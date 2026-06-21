"""文件管理服务"""
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from config.settings import settings

PENDING_PASTES_DIR = ".pending_pastes"


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
                self._base_path = Path.home() / "Documents"/ "EasyTodo" / "files"
            self._base_path.mkdir(parents=True, exist_ok=True)
        return self._base_path

    def _get_task_folder(self, todo_id: int, create: bool = False) -> Path:
        folder = self.base_path / f"task_{todo_id}"
        if create and not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    # ---- 暂存区（粘贴图片专用） ----

    @property
    def pending_root(self) -> Path:
        """粘贴图片暂存根目录"""
        root = self.base_path / PENDING_PASTES_DIR
        root.mkdir(parents=True, exist_ok=True)
        return root

    def get_pending_folder(self, pending_id: str, create: bool = True) -> Path:
        """获取/创建某个 dialog 维度的暂存目录"""
        if not pending_id:
            raise ValueError("pending_id 不能为空")
        folder = self.pending_root / pending_id
        if create and not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    def save_paste_image(self, pending_id: str, ext: str, data: bytes) -> str:
        """保存粘贴图片到暂存目录，返回存储的文件名（仅文件名，相对路径）"""
        if not ext:
            ext = "png"
        ext = ext.lstrip(".").lower()
        if ext not in {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg"}:
            ext = "png"
        folder = self.get_pending_folder(pending_id, create=True)
        filename = f"pasted_{uuid.uuid4().hex[:8]}.{ext}"
        (folder / filename).write_bytes(data)
        return filename

    def save_paste_to_task(self, pending_id: str, todo_id: int) -> List[str]:
        """把暂存目录里的所有图片 move 到 task_{todo_id}/，返回最终文件名列表"""
        if not pending_id or todo_id is None:
            return []
        pending = self.pending_root / pending_id
        if not pending.exists() or not pending.is_dir():
            return []
        task_folder = self._get_task_folder(todo_id, create=True)
        moved: List[str] = []
        try:
            for f in pending.iterdir():
                if not f.is_file():
                    continue
                dest = task_folder / f.name
                if dest.exists():
                    stem, suffix = f.stem, f.suffix
                    dest = task_folder / f"{stem}_{uuid.uuid4().hex[:6]}{suffix}"
                shutil.move(str(f), str(dest))
                moved.append(dest.name)
            shutil.rmtree(pending, ignore_errors=True)
        except Exception:
            pass
        return moved

    def cleanup_pending(self, pending_id: str):
        """清理某个 dialog 的暂存目录"""
        if not pending_id:
            return
        pending = self.pending_root / pending_id
        if pending.exists():
            shutil.rmtree(pending, ignore_errors=True)

    def save_file(self, todo_id: int, source_path: str) -> str:
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
            elif system == "Darwin":
                os.system(f'open "{task_folder}"')
            else:
                os.system(f'xdg-open "{task_folder}"')
            return True
        except Exception:
            return False

    def delete_task_folder(self, todo_id: int) -> bool:
        """删除任务关联的整个文件夹"""
        task_folder = self._get_task_folder(todo_id)

        if task_folder.exists():
            shutil.rmtree(task_folder)
            return True
        return False

    def close(self):
        pass
