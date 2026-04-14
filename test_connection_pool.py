#!/usr/bin/env python3
"""测试SSH连接池优化"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from chaos.utils.remote import SSHConnectionPool
from chaos.config import ConfigManager


def test_connection_pool_parallel():
    """测试并行获取连接"""
    config_manager = ConfigManager()
    config = config_manager.config
    
    # 获取环境配置
    env_config = config.get("environments", {}).get("1_ssh_remote")
    if not env_config:
        print("错误：未找到环境配置 '1_ssh_remote'")
        return
    
    pool = SSHConnectionPool(max_connections=10, idle_timeout=300)
    
    results = []
    lock = threading.Lock()
    
    def get_connection_task(task_id):
        """获取连接的任务"""
        try:
            start_time = time.time()
            executor = pool.get_connection(
                host=env_config.get("ip"),
                port=env_config.get("port", 22),
                user=env_config.get("user", "root"),
                passwd=env_config.get("passwd"),
                key_file=env_config.get("key_file")
            )
            end_time = time.time()
            
            # 执行一个简单的命令
            success, output = executor.execute("echo 'test'")
            
            with lock:
                results.append({
                    "task_id": task_id,
                    "success": success,
                    "duration": end_time - start_time,
                    "output": output[:50] if output else ""
                })
                print(f"任务 {task_id}: 成功={success}, 耗时={end_time - start_time:.2f}s")
        except Exception as e:
            with lock:
                results.append({
                    "task_id": task_id,
                    "success": False,
                    "error": str(e)
                })
                print(f"任务 {task_id}: 失败 - {e}")
    
    # 创建多个线程并行获取连接
    threads = []
    num_threads = 5
    
    print(f"\n开始测试并行获取连接（{num_threads} 个线程）...")
    start_time = time.time()
    
    for i in range(num_threads):
        thread = threading.Thread(target=get_connection_task, args=(i,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # 打印结果
    print(f"\n测试完成！总耗时: {total_duration:.2f}s")
    print(f"成功任务数: {sum(1 for r in results if r['success'])}/{num_threads}")
    
    # 打印详细结果
    print("\n详细结果:")
    for result in results:
        if result['success']:
            print(f"  任务 {result['task_id']}: 成功, 耗时 {result['duration']:.2f}s")
        else:
            print(f"  任务 {result['task_id']}: 失败 - {result.get('error', 'Unknown error')}")
    
    # 清理连接池
    pool.close_all()
    print("\n连接池已关闭")


if __name__ == "__main__":
    test_connection_pool_parallel()
