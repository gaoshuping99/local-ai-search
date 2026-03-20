#!/opt/anaconda3/bin/python3
"""
增量同步脚本 - 扫描文件变化并更新 Khoj 知识库
支持进度显示和增量更新
"""

import argparse
import json
import os
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple

try:
    import requests
except ImportError:
    print("错误: requests 未安装")
    print("请运行: pip install requests")
    sys.exit(1)

try:
    from markitdown import MarkItDown
except ImportError:
    print("错误: markitdown 未安装")
    print("请运行: pip install 'markitdown[xlsx,pptx]'")
    sys.exit(1)


KHOJ_URL = os.environ.get("KHOJ_URL", "http://localhost:42110")
KHOJ_API_KEY = os.environ.get("KHOJ_API_KEY", "")

SUPPORTED_FORMATS = {'.xlsx', '.xls', '.pptx', '.ppt', '.docx', '.pdf', '.md', '.txt'}
SYNC_STATE_FILE = Path.home() / ".khoj" / "sync_state.json"


class ProgressBar:
    """进度条显示"""
    
    def __init__(self, total: int, width: int = 40):
        self.total = total
        self.width = width
        self.current = 0
    
    def update(self, current: int, message: str = ""):
        self.current = current
        percent = current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        bar = '=' * filled + '>' + ' ' * (self.width - filled - 1)
        
        line = f"\r[{bar}] {percent*100:.1f}% ({current}/{self.total})"
        if message:
            line += f" {message[:30]}"
        
        print(line, end='', flush=True)
    
    def finish(self):
        print()


class SyncState:
    """同步状态管理"""
    
    def __init__(self, state_file: Path = SYNC_STATE_FILE):
        self.state_file = state_file
        self.state: Dict[str, dict] = {}
        self.load()
    
    def load(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
            except:
                self.state = {}
    
    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_file_hash(self, file_path: Path) -> str:
        """计算文件哈希（修改时间 + 大小）"""
        stat = file_path.stat()
        return f"{stat.st_mtime}_{stat.st_size}"
    
    def needs_sync(self, file_path: Path) -> bool:
        """检查文件是否需要同步"""
        key = str(file_path)
        current_hash = self.get_file_hash(file_path)
        
        if key not in self.state:
            return True
        
        return self.state[key].get('hash') != current_hash
    
    def mark_synced(self, file_path: Path, success: bool = True):
        """标记文件已同步"""
        key = str(file_path)
        self.state[key] = {
            'hash': self.get_file_hash(file_path),
            'last_sync': datetime.now().isoformat(),
            'success': success
        }
    
    def remove_file(self, file_path: Path):
        """移除文件记录"""
        key = str(file_path)
        if key in self.state:
            del self.state[key]


class KhojSyncClient:
    """Khoj 同步客户端"""
    
    def __init__(self, base_url: str = KHOJ_URL):
        self.base_url = base_url.rstrip('/')
        self.headers = {}
        if KHOJ_API_KEY:
            self.headers["Authorization"] = f"Bearer {KHOJ_API_KEY}"
    
    def is_running(self) -> bool:
        """检查服务是否运行"""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_indexed_files(self) -> Set[str]:
        """获取已索引的文件列表"""
        try:
            response = requests.get(
                f"{self.base_url}/api/content",
                headers=self.headers,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                return {item.get('file', '') for item in data if isinstance(data, list)}
        except:
            pass
        return set()
    
    def index_file(self, file_path: Path, converted_content: str = None) -> bool:
        """索引单个文件"""
        try:
            if converted_content:
                files = {'file': (file_path.name, converted_content)}
            else:
                with open(file_path, 'rb') as f:
                    files = {'file': (file_path.name, f.read())}
            
            response = requests.patch(
                f"{self.base_url}/api/content",
                headers=self.headers,
                files=files,
                timeout=60
            )
            return response.status_code == 200
        except Exception as e:
            print(f"\n  错误: {file_path.name} - {e}")
            return False


def scan_files(directory: Path) -> List[Path]:
    """扫描目录下的支持文件"""
    files = []
    for ext in SUPPORTED_FORMATS:
        files.extend(directory.rglob(f'*{ext}'))
    return sorted(files)


def convert_file(file_path: Path, md: MarkItDown) -> Tuple[bool, str]:
    """转换单个文件为 Markdown"""
    try:
        result = md.convert(file_path)
        return True, result.text_content
    except Exception as e:
        return False, str(e)


def sync_directory(
    input_dir: str,
    output_dir: str = None,
    full_sync: bool = False,
    verbose: bool = False
) -> dict:
    """
    同步目录到 Khoj 知识库
    
    返回:
        {
            'total': 总文件数,
            'indexed': 已索引数,
            'synced': 本次同步数,
            'success': 成功数,
            'failed': 失败数,
            'errors': [错误列表]
        }
    """
    input_path = Path(input_dir).expanduser().resolve()
    output_path = Path(output_dir).expanduser() if output_dir else Path("/tmp/khoj_sync")
    
    if not input_path.exists():
        print(f"错误: 目录不存在 - {input_dir}")
        sys.exit(1)
    
    # 检查服务
    client = KhojSyncClient()
    if not client.is_running():
        print("错误: Khoj 服务未运行")
        print(f"请先启动服务: khoj --anonymous-mode")
        sys.exit(1)
    
    # 初始化
    output_path.mkdir(parents=True, exist_ok=True)
    sync_state = SyncState()
    md = MarkItDown()
    
    # 扫描文件
    print(f"扫描目录: {input_path}")
    all_files = scan_files(input_path)
    print(f"找到文件: {len(all_files)} 个")
    
    # 获取已索引文件
    indexed_files = client.get_indexed_files()
    print(f"已索引: {len(indexed_files)} 个")
    
    # 确定需要同步的文件
    if full_sync:
        files_to_sync = all_files
    else:
        files_to_sync = [f for f in all_files if sync_state.needs_sync(f)]
    
    print(f"需要同步: {len(files_to_sync)} 个\n")
    
    if not files_to_sync:
        print("所有文件已是最新，无需同步")
        return {
            'total': len(all_files),
            'indexed': len(indexed_files),
            'synced': 0,
            'success': 0,
            'failed': 0,
            'errors': []
        }
    
    # 开始同步
    progress = ProgressBar(len(files_to_sync))
    success_count = 0
    failed_count = 0
    errors = []
    
    for i, file_path in enumerate(files_to_sync):
        progress.update(i + 1, file_path.name)
        
        # 转换文件
        if file_path.suffix.lower() in {'.xlsx', '.xls', '.pptx', '.ppt', '.docx', '.pdf'}:
            ok, content_or_error = convert_file(file_path, md)
            if not ok:
                failed_count += 1
                errors.append(f"{file_path.name}: {content_or_error}")
                sync_state.mark_synced(file_path, success=False)
                continue
        else:
            try:
                content_or_error = file_path.read_text(encoding='utf-8')
                ok = True
            except Exception as e:
                failed_count += 1
                errors.append(f"{file_path.name}: {e}")
                sync_state.mark_synced(file_path, success=False)
                continue
        
        # 索引文件
        if client.index_file(file_path, content_or_error if file_path.suffix.lower() in {'.xlsx', '.xls', '.pptx', '.ppt', '.docx', '.pdf'} else None):
            success_count += 1
            sync_state.mark_synced(file_path, success=True)
        else:
            failed_count += 1
            errors.append(f"{file_path.name}: 索引失败")
            sync_state.mark_synced(file_path, success=False)
        
        if verbose:
            print(f"\n  ✓ {file_path.name}")
    
    progress.finish()
    
    # 保存状态
    sync_state.save()
    
    # 输出结果
    print(f"\n✓ 成功: {success_count}")
    print(f"✗ 失败: {failed_count}")
    
    if errors and verbose:
        print("\n错误详情:")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... 还有 {len(errors) - 10} 个错误")
    
    print("\n同步完成！")
    
    return {
        'total': len(all_files),
        'indexed': len(indexed_files),
        'synced': len(files_to_sync),
        'success': success_count,
        'failed': failed_count,
        'errors': errors
    }


def main():
    parser = argparse.ArgumentParser(
        description="增量同步文件到 Khoj 知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 增量同步
  python sync.py ~/Documents
  
  # 全量同步
  python sync.py ~/Documents --full
  
  # 详细输出
  python sync.py ~/Documents --verbose
"""
    )
    
    parser.add_argument(
        "directory",
        help="要同步的目录路径"
    )
    parser.add_argument(
        "-o", "--output",
        default="/tmp/khoj_sync",
        help="转换后 Markdown 输出目录 (默认: /tmp/khoj_sync)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="强制全量同步（忽略增量判断）"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细输出"
    )
    
    args = parser.parse_args()
    
    sync_directory(
        args.directory,
        args.output,
        args.full,
        args.verbose
    )


if __name__ == "__main__":
    main()