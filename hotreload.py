#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热更新脚本 - 监控文件变化并自动重启应用
"""

import watchdog.observers
import watchdog.events
import subprocess
import time
import sys
import os
import signal

class Handler(watchdog.events.FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.restart_app()
    
    def on_modified(self, event):
        if event.src_path.endswith(".py") and "__pycache__" not in event.src_path:
            print(f"检测到文件变化: {event.src_path}")
            self.restart_app()
    
    def restart_app(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        
        print("重启应用...")
        self.process = subprocess.Popen([sys.executable, "main.py"])

def main():
    print("启动热更新监控...")
    
    observer = watchdog.observers.Observer()
    handler = Handler()
    observer.schedule(handler, ".", recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止热更新监控...")
        observer.stop()
        if handler.process:
            try:
                handler.process.terminate()
                handler.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                handler.process.kill()
                handler.process.wait()
    
    observer.join()
    print("热更新监控已停止")

if __name__ == "__main__":
    main()