@echo off
title KON Media 1.2 Rei (Native Rust Server)
set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
echo ==============================================================
echo   Starting KON Media 1.2 Rei (Native Rust Server)...
echo ==============================================================
cargo run --bin kon_media_server
pause
