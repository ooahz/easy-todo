# EasyToDo 导入导出功能重设计方案

## 一、当前问题分析

### 1. 导出问题
- **无元数据**：导出文件只是一个裸的 todo 数组，没有版本号、应用名、导出时间
- **分类数据缺失**：只导出 todo 中的 `category` 嵌套字典，没有独立导出分类列表，导入时只能靠名称匹配
- **父子关系断裂**：`pid` 使用数据库自增 ID，导入到另一个数据库时 ID 不匹配，子任务会成为孤儿
- **重复模板关系断裂**：`recurrence_template_id` 同样使用数据库 ID，导入后实例与模板的关联丢失
- **导出内容不完整**：只导出 `get_all_including_done()`（不含已归档），重复模板也不导出

### 2. 导入问题
- **字段清理脆弱**：手动列举要删除的字段（`id`, `created_at`, `children` 等），容易遗漏或误删
- **分类处理不健壮**：虽然已修复 `category` 嵌套字典问题，但只按名称匹配，颜色等信息丢失
- **父子关系未处理**：导入时 `pid` 被删除（在清理列表中），子任务全部变成顶级任务
- **重复任务未处理**：`recurrence_template_id` 被删除，重复实例变成普通任务
- **无导入模式选择**：不支持"合并导入"vs"替换导入"
- **无导入预览**：用户无法在导入前看到将要导入的内容
- **无进度提示**：大量数据导入时界面无反馈
- **去重策略简陋**：仅按 ID 精确匹配，跨数据库 ID 无意义

### 3. 架构问题
- **逻辑耦合**：导入导出逻辑全部写在 `main_window.py` 中（约 80 行），违反单一职责
- **无独立服务层**：没有专门的 `ImportExportService`，业务逻辑和 UI 逻辑混杂
- **无版本兼容**：文件格式无版本号，未来格式变更无法兼容

---

## 二、新方案设计

### 1. 导出文件格式 v2

```json
{
  "version": "2.0",
  "app": "EasyTodo",
  "exported_at": "2026-05-30T12:00:00",
  "categories": [
    {
      "name": "工作",
      "color": "#0078D4",
      "sort_order": 0
    }
  ],
  "todos": [
    {
      "title": "项目计划",
      "description": "...",
      "priority": 3,
      "status": 0,
      "color_tag": "#D13438",
      "due_date": "2026-06-01",
      "auto_postpone": false,
      "sort_order": 0,
      "category_name": "工作",
      "recurrence_type": "weekly",
      "recurrence_interval": 1,
      "recurrence_day": 1,
      "recurrence_end_date": null,
      "is_recurrence_template": true,
      "children": [
        {
          "title": "子任务1",
          "description": "",
          "priority": 0,
          "sort_order": 0,
          "category_name": "工作"
        }
      ],
      "instances": [
        {
          "title": "项目计划",
          "due_date": "2026-06-08",
          "occurrence_date": "2026-06-08",
          "status": 0,
          "is_exception": false,
          "children": []
        }
      ]
    }
  ]
}
```

**关键设计决策**：
- **树形结构**：子任务嵌套在 `children` 中，不再依赖 `pid` ID 引用
- **重复实例嵌套**：重复实例嵌套在模板的 `instances` 中，不再依赖 `recurrence_template_id` ID 引用
- **分类用名称**：使用 `category_name` 替代 `category_id`，跨数据库可移植
- **排除自动生成字段**：`id`, `pid`, `category_id`, `recurrence_template_id`, `created_at`, `updated_at` 不导出
- **独立分类列表**：`categories` 数组保留完整的分类信息（颜色、排序）

### 2. 导入策略

#### 导入模式
- **合并导入**（默认）：将导入数据追加到现有数据中，保留现有数据
- **替换导入**：清空现有所有任务和分类，然后导入

#### 分类处理
1. 读取导入文件中的 `categories` 列表
2. 对每个分类按名称匹配现有分类
3. 名称匹配到 → 复用现有分类 ID
4. 名称未匹配 → 自动创建新分类（保留颜色信息）
5. 导入文件中无 `categories` 但 todo 有 `category_name` → 按名称匹配/创建

#### 父子关系重建
1. 遍历 todo 树，先创建父任务获得新 ID
2. 再遍历 `children`，将 `pid` 设为新父任务 ID 后创建子任务

#### 重复模板重建
1. 创建模板任务，获得新模板 ID
2. 遍历 `instances`，将 `recurrence_template_id` 设为新模板 ID 后创建实例
3. 遍历实例的 `children`，将 `pid` 设为新实例 ID 后创建子任务

#### 去重策略
- 合并模式下，按 `title + due_date + category_name` 三元组判断是否重复
- 替换模式下无需去重

#### 版本兼容
- 检测 `version` 字段，v2 格式走新逻辑
- 无 `version` 字段视为 v1 格式，走兼容逻辑（当前逻辑的改进版）

### 3. 新增文件

#### `services/import_export_service.py`
独立的导入导出服务，负责：
- `export_data()` → 返回格式化的导出字典
- `import_data(data, mode="merge")` → 执行导入，返回结果统计
- `_build_export_tree()` → 构建导出树形结构
- `_import_v1(data, mode)` → 兼容 v1 格式
- `_import_v2(data, mode)` → 处理 v2 格式
- `_match_or_create_category()` → 分类匹配/创建
- `_import_todo_node()` → 递归导入 todo 节点（含 children 和 instances）

#### `views/import_preview_dialog.py`
导入预览弹窗（继承 `MessageBoxBase`），展示：
- 导入模式选择（合并/替换）
- 将导入的分类数量
- 将导入的任务数量（含子任务和重复实例）
- 重复任务数量（合并模式下）
- 确认/取消按钮

### 4. 修改文件

#### `models/todo.py`
- 新增 `to_export_dict()` 方法：导出专用序列化，排除 ID 字段，使用 `category_name`，嵌套 `children` 和 `instances`

#### `views/main_window.py`
- 删除 `_export_data()` 和 `_import_data()` 中的业务逻辑
- 改为调用 `ImportExportService`
- 导入前弹出 `ImportPreviewDialog`

#### `views/settings_dialog.py`
- 无需修改，按钮和信号连接保持不变

---

## 三、实施步骤

### 步骤 1：创建 `ImportExportService`
- 新建 `services/import_export_service.py`
- 实现 `export_data()` 方法：查询所有分类、所有任务（含已归档和模板），构建 v2 格式
- 实现 `import_data()` 方法：v1/v2 格式检测，分类处理，树形递归导入

### 步骤 2：修改 `Todo.to_export_dict()`
- 在 `models/todo.py` 中新增 `to_export_dict()` 方法
- 排除 `id`, `pid`, `category_id`, `recurrence_template_id`, `created_at`, `updated_at`
- 使用 `category_name` 替代 `category_id`
- 不包含 `children` 和 `instances`（由 export 服务负责组装）

### 步骤 3：创建 `ImportPreviewDialog`
- 新建 `views/import_preview_dialog.py`
- 继承 `MessageBoxBase`，保持与现有弹窗一致的样式
- 显示导入统计信息和模式选择

### 步骤 4：重构 `main_window.py` 中的导入导出
- `_export_data()` 改为调用 `ImportExportService.export_data()` + 写文件
- `_import_data()` 改为读文件 + `ImportPreviewDialog` + `ImportExportService.import_data()`
- 删除原有的内联业务逻辑

### 步骤 5：测试验证
- 语法检查
- 导出 → 检查 JSON 格式正确性
- 导入 v2 格式 → 验证分类、父子关系、重复模板正确还原
- 导入 v1 格式（旧备份文件）→ 验证兼容性
- 合并模式 → 验证去重
- 替换模式 → 验证清空后导入

---

## 四、详细代码设计

### `services/import_export_service.py` 核心逻辑

```python
class ImportExportService:
    EXPORT_VERSION = "2.0"

    def __init__(self, todo_service, category_service):
        self.todo_service = todo_service
        self.category_service = category_service

    def export_data(self) -> dict:
        """导出全部数据为 v2 格式"""
        categories = self.category_service.get_all()
        all_todos = self.todo_service.get_all_including_archived()  # 需新增

        # 构建分类列表
        cat_list = []
        for cat in categories:
            if not cat.is_system:
                cat_list.append({
                    "name": cat.name,
                    "color": cat.color,
                    "sort_order": cat.sort_order,
                })

        # 构建任务树（含模板+实例）
        todo_list = self._build_export_tree(all_todos)

        return {
            "version": self.EXPORT_VERSION,
            "app": "EasyTodo",
            "exported_at": datetime.now().isoformat(),
            "categories": cat_list,
            "todos": todo_list,
        }

    def _build_export_tree(self, todos) -> list[dict]:
        """构建导出树：顶级任务 → children → instances → instance.children"""
        # 分组：顶级非模板、模板、子任务、实例
        top_level = []    # pid=None, is_recurrence_template=False
        templates = []    # pid=None, is_recurrence_template=True
        children_map = {} # parent_id -> [child_todo]
        instances_map = {} # template_id -> [instance_todo]
        instance_children_map = {} # instance_id -> [child_todo]

        for t in todos:
            if t.pid is None and not t.is_recurrence_template:
                top_level.append(t)
            elif t.pid is None and t.is_recurrence_template:
                templates.append(t)
            elif t.recurrence_template_id is not None:
                # 重复实例的子任务
                instance_children_map.setdefault(t.pid, []).append(t)
            elif t.pid is not None:
                # 判断是否为模板的蓝图子任务 或 实例的子任务
                parent = ... # 需要查找父任务
                if parent and parent.is_recurrence_template:
                    # 模板蓝图子任务，不导出（会从模板重建）
                    pass
                else:
                    children_map.setdefault(t.pid, []).append(t)

        # ... 构建树形结构
```

### `models/todo.py` - `to_export_dict()`

```python
def to_export_dict(self) -> dict:
    """导出专用序列化，排除 ID 和内部引用字段"""
    return {
        "title": self.title,
        "description": self.description or "",
        "priority": self.priority,
        "status": self.status,
        "color_tag": self.color_tag,
        "due_date": self.due_date.isoformat() if self.due_date else None,
        "auto_postpone": self.auto_postpone,
        "sort_order": self.sort_order,
        "category_name": self.category.name if self.category else None,
        "recurrence_type": self.recurrence_type,
        "recurrence_interval": self.recurrence_interval,
        "recurrence_day": self.recurrence_day,
        "recurrence_end_date": self.recurrence_end_date.isoformat() if self.recurrence_end_date else None,
        "is_recurrence_template": self.is_recurrence_template,
        "occurrence_date": self.occurrence_date.isoformat() if self.occurrence_date else None,
        "is_exception": self.is_exception,
    }
```

### `views/import_preview_dialog.py`

```python
class ImportPreviewDialog(MessageBoxBase):
    """导入预览弹窗"""
    def __init__(self, preview_data: dict, parent=None):
        super().__init__(parent)
        # preview_data 包含:
        # - categories_count, todos_count, children_count
        # - instances_count, duplicate_count
        # - mode: "merge" | "replace"
        # 构建 UI: 统计信息 + 模式选择 Radio
```

### `main_window.py` - 重构后的导入导出

```python
def _export_data(self):
    path, _ = QFileDialog.getSaveFileName(
        self, "导出数据", "easy_todo_backup.json", "JSON 文件 (*.json)")
    if not path:
        return
    try:
        service = ImportExportService(self.todo_service, self.category_service)
        data = service.export_data()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        todo_count = len(data.get("todos", []))
        InfoBar.success(title="导出成功", content=f"已导出 {todo_count} 个任务", ...)
    except Exception as e:
        InfoBar.error(title="导出失败", content=str(e), ...)

def _import_data(self):
    path, _ = QFileDialog.getOpenFileName(
        self, "导入数据", "", "JSON 文件 (*.json)")
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        service = ImportExportService(self.todo_service, self.category_service)
        preview = service.preview(data)  # 预计算统计
        dlg = ImportPreviewDialog(preview, parent=self)
        if not dlg.exec():
            return
        mode = dlg.selected_mode  # "merge" or "replace"
        result = service.import_data(data, mode=mode)
        self._refresh_all_views()
        InfoBar.success(title="导入成功",
            content=f"已导入 {result['imported']} 个任务，{result['categories']} 个分类", ...)
    except Exception as e:
        InfoBar.error(title="导入失败", content=str(e), ...)
```

---

## 五、需要新增的 Service 方法

### `TodoService` 新增
- `get_all_including_archived()` → 查询所有状态的任务（含已归档），用于完整导出
- `get_template_instances(template_id)` → 获取模板的所有实例
- `get_template_blueprints(template_id)` → 获取模板的蓝图子任务

### `CategoryService` 新增
- `get_by_name(name)` → 按名称查找分类（用于导入匹配）

---

## 六、边界情况处理

1. **空文件导入**：提示"文件格式不正确"
2. **v1 格式兼容**：检测无 `version` 字段时走旧逻辑（改进版）
3. **导入文件分类为空但 todo 有 category_name**：按名称匹配/创建
4. **重复模板的蓝图子任务**：导出时不单独导出，导入时从模板自动生成
5. **已归档任务**：v2 格式导出包含已归档任务，导入时保留归档状态
6. **替换模式确认**：替换导入前在预览弹窗中二次确认
7. **导入中断**：使用数据库事务，失败时回滚
