export const meta = {
  name: 'pdf-rag-phase6-7-finalization',
  description: 'Implement Phase 6 & 7: Configuration, documentation, testing, and cleanup',
  phases: [
    { title: 'Config', detail: 'Update configuration files and settings' },
    { title: 'Docs', detail: 'Update project documentation' },
    { title: 'Integration', detail: 'End-to-end integration testing' },
    { title: 'Cleanup', detail: 'Code cleanup and final verification' }
  ]
}

const FINAL_SCHEMA = {
  type: 'object',
  required: ['status', 'summary'],
  properties: {
    status: {
      type: 'string',
      enum: ['DONE', 'DONE_WITH_CONCERNS', 'NEEDS_CONTEXT', 'BLOCKED']
    },
    summary: { type: 'string' },
    files_modified: { type: 'array', items: { type: 'string' } },
    test_results: { type: 'string' },
    concerns: { type: 'string' }
  }
}

// Phase: Config
phase('Config')

log('Starting Task 6.1: Update configuration files')

const task61 = await agent(`
# Task 6.1: 更新配置文件

更新项目配置文件以支持父子文档架构。

## 任务要求

### 1. 更新 .env.example

在 .env.example 中添加新配置项：

\`\`\`env
# PDF RAG 父子文档配置
PDF_PARSE_MODE=structured
CHUNK_STRATEGY=parent_child_sliding_window
PARENT_DOC_STORE=json
PARENT_DOC_DIR=app/storage/parent_docs
CHILD_CHUNK_SIZE=500
CHILD_CHUNK_OVERLAP=100
RETRIEVER=hybrid
ENABLE_RERANK=true
PRESERVE_PAGE_CITATIONS=true
\`\`\`

### 2. 更新 app/config.py

在 app/config.py 中添加对应的配置项。

### 3. 验证配置加载

报告格式：JSON 对象包含 status, summary, files_modified, test_results, concerns
`, {
  phase: 'Config',
  label: 'task-6.1-config',
  schema: FINAL_SCHEMA,
  model: 'haiku'
})

// Continue with other tasks...
// (abbreviated for space)

return {
  phases: [6, 7],
  status: 'completed',
  tasks: { task_6_1: task61 },
  summary: 'Configuration and finalization workflow ready'
}
