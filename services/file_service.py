"""文件管理服务 - 管理任务关联文件"""
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from config.settings import settings


class FileService:
    """文件管理服务"""

    def __init__(self):
        self._base_path: Optional[Path] = None

    @property
    def base_path(self) -> Path:
        """获取数据保存路径"""
        if self._base_path is None:
            path = settings.data_path
            if path:
                self._base_path = Path(path)
            else:
                # 默认路径：应用数据目录
                from config.constants import APP_ID
                self._base_path = Path.home() / f".{APP_ID}" / "files"
            self._base_path.mkdir(parents=True, exist_ok=True)
        return self._base_path

    def _get_task_folder(self, todo_id: int, create: bool = False) -> Path:
        """获取任务关联文件夹路径
        
        :param todo_id: 任务ID
        :param create: 是否创建文件夹（仅在保存文件时为True）
        """
        folder = self.base_path / f"task_{todo_id}"
        if create and not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    def save_file(self, todo_id: int, source_path: str) -> str:
        """
        保存文件到任务关联文件夹
        :param todo_id: 任务ID
        :param source_path: 源文件路径
        :return: 保存后的文件名
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"文件不存在: {source_path}")

        task_folder = self._get_task_folder(todo_id, create=True)

        # 生成唯一文件名避免冲突
        original_name = source.name
        name_parts = original_name.rsplit(".", 1)
        if len(name_parts) == 2:
            base_name, ext = name_parts
            new_name = f"{base_name}_{uuid.uuid4().hex[:8]}.{ext}"
        else:
            new_name = f"{original_name}_{uuid.uuid4().hex[:8]}"

        dest_path = task_folder / new_name
        shutil.copy2(source_path, dest_path)
        return new_name

    def get_files(self, todo_id: int) -> List[dict]:
        """
        获取任务关联的所有文件
        :param todo_id: 任务ID
        :return: 文件信息列表
        """
        task_folder = self._get_task_folder(todo_id)
        files = []

        if not task_folder.exists():
            return files

        for file_path in task_folder.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })

        # 按修改时间排序
        files.sort(key=lambda x: x["modified"], reverse=True)
        return files

    def get_file_count(self, todo_id: int) -> int:
        """获取任务关联文件数量"""
        task_folder = self._get_task_folder(todo_id)
        if not task_folder.exists():
            return 0
        return sum(1 for f in task_folder.iterdir() if f.is_file())

    def delete_file(self, todo_id: int, filename: str) -> bool:
        """删除任务关联的指定文件"""
        task_folder = self._get_task_folder(todo_id)
        file_path = task_folder / filename

        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            return True
        return False

    def open_folder(self, todo_id: int) -> bool:
        """打开任务关联文件夹"""
        task_folder = self._get_task_folder(todo_id)

        if not task_folder.exists():
            return False

        # 跨平台打开文件夹
        import platform
        system = platform.system()

        try:
            if system == "Windows":
                os.startfile(str(task_folder))
            elif system == "Darwin":  # macOS
                os.system(f'open "{task_folder}"')
            else:  # Linux
                os.system(f'xdg-open "{task_folder}"')
            return True
        except Exception:
            return False

    def delete_task_folder(self, todo_id: int) -> bool:
        """删除任务关联的整个文件夹（任务删除时调用）"""
        task_folder = self._get_task_folder(todo_id)

        if task_folder.exists():
            shutil.rmtree(task_folder)
            return True
        return False
