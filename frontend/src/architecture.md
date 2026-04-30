# Frontend Architecture Notes

## 推荐技术方向

- Vue 3
- Router
- Pinia 或 composables state
- 卡片式后台布局
- 平台动态表单 schema 渲染

## 组件建议

- `layout/`
  - `AppShell`
  - `TheHeader`
  - `TheSidebar`
- `tasks/`
  - `TasksTable`
  - `TaskEditor`
  - `PlatformTaskFormRenderer`
- `datasets/`
  - `DatasetTable`
  - `DatasetPreviewPanel`
- `analysis/`
  - `AnalysisOverview`
  - `PlatformAnalysisPanel`
  - `CrossPlatformPanel`
- `reports/`
  - `ReportList`
  - `ReportViewer`
