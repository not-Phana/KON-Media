$env:Path = "$HOME\.cargo\bin;$env:Path"
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  Starting KON Media 1.2 Rei Carbon (Native Rust Server)" -ForegroundColor Cyan
Write-Host "  Engine: rust-core/1.2.0 | High-Speed Async Tokio Runtime" -ForegroundColor DarkGray
Write-Host "==============================================================" -ForegroundColor DarkGray
cargo run --bin kon_media_server
