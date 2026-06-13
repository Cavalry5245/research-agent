# 性能测试套件

## 📖 概述

这个目录包含了 ResearchAgent 的完整性能基准测试套件，用于评估系统在各种负载下的表现。

## 🎯 测试覆盖

| 测试文件 | 测试内容 | 关键指标 |
|---------|---------|---------|
| `test_embedding_perf.py` | Embedding性能 | 单次延迟、吞吐量、冷/热启动 |
| `test_vector_store_perf.py` | 向量存储性能 | 索引速度、查询延迟、并发性能、内存占用 |
| `test_qa_e2e_perf.py` | QA端到端性能 | 延迟分布、QPS、各阶段耗时占比 |
| `test_stress.py` | 压力测试 | 最大并发数、持续负载、内存泄漏检测 |

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install pytest psutil
```

### 2. 运行完整性能测试

```bash
# 运行所有性能测试（耗时约10-20分钟）
python tests/performance/run_benchmarks.py

# 生成可视化报告
python tests/performance/generate_report.py
```

### 3. 运行单个测试

```bash
# 只测试Embedding性能
pytest tests/performance/test_embedding_perf.py -v -s

# 只测试QA端到端性能
pytest tests/performance/test_qa_e2e_perf.py -v -s

# 只运行压力测试
pytest tests/performance/test_stress.py -v -s
```

## 📊 性能目标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **QA P50延迟** | <500ms | 50%的查询应在0.5秒内返回 |
| **QA P95延迟** | <2000ms | 95%的查询应在2秒内返回 |
| **QA QPS** | >1 (单机) | 单机每秒至少处理1个查询 |
| **Embedding P95** | <100ms | 95%的embedding请求<100ms |
| **向量查询P95** | <500ms | 95%的向量查询<500ms |
| **内存占用** | <2GB | 5000 chunks索引占用<2GB |
| **并发支持** | >5 concurrent | 支持至少5个并发查询 |

## 📈 如何解读结果

### 延迟分解示例

```
=== QA Latency Breakdown ===
Embedding:    50.23ms (10.2%)  ← embedding查询编码
Retrieval:    80.45ms (16.3%)  ← 向量检索
LLM Gen:     362.18ms (73.5%)  ← LLM生成答案
Total:       492.86ms
```

**分析**：LLM生成占73.5%，是主要瓶颈。优化方向：
- 减少生成token数
- 使用更快的模型
- 添加答案缓存

### 吞吐量示例

```
=== QA Throughput ===
处理20个问题，耗时45.32s
QPS: 0.44 questions/sec
```

**分析**：QPS=0.44，低于目标1.0。可能原因：
- LLM调用串行
- 没有并发优化
- 网络延迟

## 🔧 调优建议

### 低延迟优化（降低P95）

1. **缓存热点查询**
   ```python
   # 添加 LRU Cache
   from functools import lru_cache
   
   @lru_cache(maxsize=100)
   def answer_question_cached(question, paper_id):
       ...
   ```

2. **并行化embedding和检索**
   ```python
   import asyncio
   
   async def parallel_qa():
       emb_task = asyncio.create_task(embed_query(question))
       # ...
   ```

3. **使用更快的embedding模型**
   - bge-small-zh → all-MiniLM-L6-v2 (更快)
   - 考虑量化模型

### 高吞吐优化（提升QPS）

1. **批量处理**
   ```python
   # 批量embedding
   embeddings = embedding_client.embed_batch(questions)
   ```

2. **异步LLM调用**
   ```python
   import asyncio
   from openai import AsyncOpenAI
   
   async def async_generate(prompt):
       ...
   ```

3. **连接池复用**
   ```python
   # 复用HTTP连接
   from requests.adapters import HTTPAdapter
   session.mount('http://', HTTPAdapter(pool_connections=10))
   ```

### 内存优化

1. **分页加载向量**
2. **定期清理缓存**
3. **使用轻量级embedding模型**

## 📝 CI/CD集成

将性能测试加入CI流程：

```yaml
# .github/workflows/performance.yml
name: Performance Tests

on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 0 * * 0'  # 每周日运行

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run benchmarks
        run: |
          python tests/performance/run_benchmarks.py
      - name: Generate report
        run: |
          python tests/performance/generate_report.py
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: performance-results
          path: tests/performance/results/
```

## 🎤 面试话术

### 问题1：你如何测试系统性能？

> "我建立了完整的性能测试套件，分为四个层次：
> 
> 1. **单元性能测试** - 测试各个组件（embedding、向量存储）的延迟和吞吐
> 2. **端到端性能测试** - 测试完整QA流程的P50/P95/P99延迟
> 3. **并发性能测试** - 测试不同并发数下的QPS和延迟
> 4. **压力测试** - 找到系统极限，检测内存泄漏
> 
> 测试结果显示，QA P95延迟在800ms左右，单机QPS能达到1.5，满足我们的目标。"

### 问题2：遇到性能瓶颈如何定位？

> "我用延迟分解法定位瓶颈。比如发现QA延迟2秒，我拆分成：
> - Embedding: 50ms (2.5%)
> - 向量检索: 100ms (5%)
> - LLM生成: 1850ms (92.5%)
> 
> 明显LLM是瓶颈，于是我做了三个优化：
> 1. 减少prompt token数（从2000降到800）
> 2. 添加结果缓存（命中率30%）
> 3. 使用更快的模型（qwen-turbo）
> 
> 最终P95降到了800ms。"

### 问题3：如何保证生产环境性能？

> "三个层面：
> 1. **基准测试** - 每次PR都跑性能测试，防止回退
> 2. **监控告警** - 部署Prometheus，设置P95延迟>2s告警
> 3. **定期压测** - 每周跑一次压力测试，检测内存泄漏
> 
> 同时保留历史基准数据，可以看到性能趋势。"

## 📚 参考资料

- [Load Testing Best Practices](https://grafana.com/load-testing/)
- [Python Performance Testing](https://realpython.com/python-performance-testing/)
- [Vector Database Benchmarks](https://github.com/erikbern/ann-benchmarks)

## 🤝 贡献

发现新的性能瓶颈？欢迎添加新的测试case！

1. 在对应的测试文件中添加新的test方法
2. 确保测试有clear的断言和print输出
3. 更新本README的性能目标表格
