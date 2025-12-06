import subprocess
import time
import threading
from datetime import datetime

APP_FILE = "app.py"
RESTART_INTERVAL = 3600  # 1小时 = 3600秒

def wait_and_restart(process, interval):
    """等待指定时间后设置重启标志"""
    time.sleep(interval)
    global should_restart
    should_restart = True

while True:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动Streamlit应用...")
    
    should_restart = False
    restart_timer = None
    
    try:
        # 启动Streamlit应用
        process = subprocess.Popen([
            "python", "-m", "streamlit", "run", APP_FILE,
            "--server.address", "0.0.0.0",
            "--server.port", "9999"
        ])
        
        # 启动定时重启线程
        restart_timer = threading.Thread(target=wait_and_restart, args=(process, RESTART_INTERVAL))
        restart_timer.daemon = True
        restart_timer.start()
        
        # 主循环：检查应用状态
        while True:
            # 检查应用是否意外退出
            if process.poll() is not None:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 应用意外退出")
                break
            
            # 检查是否到达重启时间
            if should_restart:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 到达重启时间 ({RESTART_INTERVAL}秒)")
                break
            
            # 每秒检查一次
            time.sleep(1)
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 错误: {e}")
    
    # 终止应用进程
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在停止应用...")
    try:
        process.terminate()
        process.wait(timeout=10)
    except:
        process.kill()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 等待5秒后重启...")
    time.sleep(5)