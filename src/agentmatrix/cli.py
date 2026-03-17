"""
AgentMatrix CLI - 命令行接口

提供命令行工具来启动和管理 AgentMatrix 服务。
"""

import sys
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="AgentMatrix CLI")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # start 命令
    start_parser = subparsers.add_parser('start', help='启动 AgentMatrix 服务')
    start_parser.add_argument('--matrix-world', type=str, default='./MatrixWorld',
                             help='MatrixWorld 目录路径')
    start_parser.add_argument('--host', type=str, default='127.0.0.1',
                             help='服务器地址')
    start_parser.add_argument('--port', type=int, default=8000,
                             help='服务器端口')
    
    # version 命令
    subparsers.add_parser('version', help='显示版本信息')
    
    args = parser.parse_args()
    
    if args.command == 'start':
        # 导入并启动服务器
        from . import server
        
        # 设置命令行参数
        sys.argv = [
            'agentmatrix',
            '--matrix-world', args.matrix_world,
            '--host', args.host,
            '--port', str(args.port)
        ]
        
        # 启动服务器
        print(f"🚀 Starting AgentMatrix service...")
        print(f"   MatrixWorld: {args.matrix_world}")
        print(f"   Server: http://{args.host}:{args.port}")
        
        import uvicorn
        uvicorn.run(
            server.app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
    
    elif args.command == 'version':
        print("AgentMatrix v1.0.0")
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
