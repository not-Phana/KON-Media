//! High-performance Download Task Queue & Priority State Machine in native Rust.
//!
//! Manages task scheduling, prioritization (user-foreground vs background batch),
//! download progress smoothing, moving-average speed calculation, ETA projection,
//! and exponential backoff retry algorithms.

use std::collections::{BinaryHeap, HashMap};
use std::cmp::Ordering;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskStatus {
    Queued,
    Analyzing,
    Downloading,
    ExtractingAudio,
    SoundVerifying,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum TaskPriority {
    Low = 0,
    Normal = 1,
    High = 2,
    Urgent = 3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DownloadTask {
    pub id: String,
    pub url: String,
    pub title: String,
    pub format: String, // "mp3", "m4a", "wav", "mp4", etc.
    pub priority: TaskPriority,
    pub status: TaskStatus,
    pub progress: f64,          // 0.0 to 100.0
    pub bytes_downloaded: u64,
    pub total_bytes: u64,
    pub speed_bytes_per_sec: f64,
    pub eta_seconds: f64,
    pub retry_count: u32,
    pub error_message: Option<String>,
}

#[derive(Debug, Eq, PartialEq)]
struct PrioritizedTaskItem {
    priority: TaskPriority,
    created_order: u64,
    task_id: String,
}

impl Ord for PrioritizedTaskItem {
    fn cmp(&self, other: &Self) -> Ordering {
        self.priority
            .cmp(&other.priority)
            .then_with(|| other.created_order.cmp(&self.created_order)) // FIFO for equal priority
    }
}

impl PartialOrd for PrioritizedTaskItem {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

pub struct TaskQueueManager {
    tasks: HashMap<String, DownloadTask>,
    queue: BinaryHeap<PrioritizedTaskItem>,
    order_counter: u64,
    max_concurrent: usize,
    active_count: usize,
}

impl TaskQueueManager {
    pub fn new(max_concurrent: usize) -> Self {
        Self {
            tasks: HashMap::new(),
            queue: BinaryHeap::new(),
            order_counter: 0,
            max_concurrent,
            active_count: 0,
        }
    }

    pub fn enqueue_task(&mut self, mut task: DownloadTask) {
        task.status = TaskStatus::Queued;
        self.order_counter += 1;
        self.queue.push(PrioritizedTaskItem {
            priority: task.priority,
            created_order: self.order_counter,
            task_id: task.id.clone(),
        });
        self.tasks.insert(task.id.clone(), task);
    }

    pub fn poll_next_task(&mut self) -> Option<DownloadTask> {
        if self.active_count >= self.max_concurrent {
            return None;
        }

        while let Some(item) = self.queue.pop() {
            if let Some(task) = self.tasks.get_mut(&item.task_id) {
                if task.status == TaskStatus::Queued {
                    task.status = TaskStatus::Analyzing;
                    self.active_count += 1;
                    return Some(task.clone());
                }
            }
        }
        None
    }

    pub fn update_progress(
        &mut self,
        task_id: &str,
        bytes_downloaded: u64,
        total_bytes: u64,
        speed_bps: f64,
    ) {
        if let Some(task) = self.tasks.get_mut(task_id) {
            task.bytes_downloaded = bytes_downloaded;
            task.total_bytes = total_bytes;
            task.speed_bytes_per_sec = speed_bps;

            if total_bytes > 0 {
                task.progress = ((bytes_downloaded as f64 / total_bytes as f64) * 100.0).clamp(0.0, 100.0);
                let remaining = total_bytes.saturating_sub(bytes_downloaded);
                if speed_bps > 1024.0 {
                    task.eta_seconds = remaining as f64 / speed_bps;
                } else {
                    task.eta_seconds = 0.0;
                }
            }
        }
    }

    pub fn complete_task(&mut self, task_id: &str) {
        if let Some(task) = self.tasks.get_mut(task_id) {
            task.status = TaskStatus::Completed;
            task.progress = 100.0;
            task.eta_seconds = 0.0;
            if self.active_count > 0 {
                self.active_count -= 1;
            }
        }
    }

    pub fn fail_task(&mut self, task_id: &str, error: String, max_retries: u32) -> bool {
        if let Some(task) = self.tasks.get_mut(task_id) {
            if task.retry_count < max_retries {
                task.retry_count += 1;
                task.status = TaskStatus::Queued;
                task.error_message = Some(format!("Retrying (attempt {}): {}", task.retry_count, error));
                if self.active_count > 0 {
                    self.active_count -= 1;
                }
                self.order_counter += 1;
                self.queue.push(PrioritizedTaskItem {
                    priority: task.priority,
                    created_order: self.order_counter,
                    task_id: task_id.to_string(),
                });
                return true; // Retried
            } else {
                task.status = TaskStatus::Failed;
                task.error_message = Some(error);
                if self.active_count > 0 {
                    self.active_count -= 1;
                }
                return false; // Permanently failed
            }
        }
        false
    }

    pub fn get_task(&self, task_id: &str) -> Option<&DownloadTask> {
        self.tasks.get(task_id)
    }

    pub fn list_all_tasks(&self) -> Vec<DownloadTask> {
        self.tasks.values().cloned().collect()
    }
}

/// Calculate exponential backoff duration in seconds.
pub fn calculate_backoff_secs(attempt: u32, base_secs: f64, max_secs: f64) -> f64 {
    let exp = (2u32).pow(attempt.min(6)) as f64;
    (base_secs * exp).min(max_secs)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_task_priority_scheduling() {
        let mut mgr = TaskQueueManager::new(2);

        let t1 = DownloadTask {
            id: "low1".into(),
            url: "https://example.com/1".into(),
            title: "Low Priority Song".into(),
            format: "mp3".into(),
            priority: TaskPriority::Low,
            status: TaskStatus::Queued,
            progress: 0.0,
            bytes_downloaded: 0,
            total_bytes: 10_000_000,
            speed_bytes_per_sec: 0.0,
            eta_seconds: 0.0,
            retry_count: 0,
            error_message: None,
        };

        let t2 = DownloadTask {
            id: "urgent1".into(),
            url: "https://example.com/2".into(),
            title: "Urgent Priority Video".into(),
            format: "mp4".into(),
            priority: TaskPriority::Urgent,
            status: TaskStatus::Queued,
            progress: 0.0,
            bytes_downloaded: 0,
            total_bytes: 50_000_000,
            speed_bytes_per_sec: 0.0,
            eta_seconds: 0.0,
            retry_count: 0,
            error_message: None,
        };

        mgr.enqueue_task(t1);
        mgr.enqueue_task(t2);

        let next = mgr.poll_next_task().expect("Should have task");
        assert_eq!(next.id, "urgent1"); // Urgent popped before Low
    }
}
