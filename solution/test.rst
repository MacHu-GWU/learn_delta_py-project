
Solution Overview
------------------------------------------------------------------------------
.. note::

    这个 Solution 的目标是将某个 Transactional Database 中的单个 Table 中的数据以近实时的方式同步到 DataLake 中. 如果你有多个 Table 需要同步, 只需要为每个 Table 重复这个 Solution 的步骤即可.

我们以一个从 2021-01-01 00:00:00 开始运行的数据表为例. 假设当前是 2024-01-01 00:00:00, 我们决定将这个表的数据同步到 DataLake 中.

不管这个表是什么样的, 它一定会有下面这三个字段:

- id: 唯一决定这一条数据. 不一定是单个 field, 也可以是多个 field 的组合 (compound key).
- create_time: 这条记录的创建时间.
- update_time: 这条记录的最后更新时间. 如果这条记录是第一次被创建, 那么这个时间和 create_time 是一样的.

.. code-block:: python

    {
        "id": "id-1",
        "create_time": "2021-01-01T00:00:00.123Z",
        "update_time": "2021-01-01T00:00:00.123Z",
        "...": "..."
    }

1. 配置 CDC Stream.

- 1.1 配置数据库 CDC Event Stream, 让从某个时间节点 (我们称之为 "Initial Time") 开始不断捕获 CDC 数据并将其发送到到 Stream 中. 这个 Stream 中的数据的 "Event Time" 就是我们数据中的 "update_time".
- 1.2 我们配置一个 "CDC Data Persistence Consumer", 按照 "update_time" 排序将数据按照一定的 time interval, 例如 1 分钟一个区间, 持久化到 Object Storage 系统中. 例如你会有 "2024-01-01T00:00-to-2024-01-01T00:01", "2024-01-01T00:01-to-2024-01-01T00:02", ... 这样的数据文件. 每一个数据文件我们叫做 "CDC Time Slice File".

2. 创建 Initial Datalake.

- 2.1 我们用数据库在某个时间点 (我们称之为 "Snapshot Cutoff Time") 的 Snapshot 中的数据初始化一个 Datalake. 这样批量导出数据到 Datalake 中不会影响数据库本身的业务. 使用 Snapshot 并不是唯一的方式, 还有的数据库支持 export, 或是 WAL (write-ahead logging) export 的方式. 但目的是一样的.
- 2.2 在创建 Datalake 时我们要选择一个 data partition key, 通常一定会被使用的 partition key 是 "create_time" (除此之外你可以添加更多的 partition key), 因为 "create_time" 在一条记录一旦被创建后就不会改变, 这样哪怕这条记录被更新了, 它所在的 partition 也不会变. 换言之, 选做 partition key 的字段一定是 immutable 的.

3. 创建 CDC Data Pipeline

- 3.1 创建一个中心化的 metadata store, 当做分布式锁, 用来管理 Pipeline 的运行状态.
- 3.2 创建一个 Orchestrator, 用来调度 CDC Data Pipeline 的运行.
- 3.3 创建一个 CDC Data Processing Worker, 用来将 CDC Data 写入到 Datalake 中.
- 3.4 Worker 的业务逻辑如下.
    - 尝试到 metadata store 中获取锁, 如果失败则说明有其他 Worker 正在运行, 则直接退出.
    - 获得锁, 然后根据上一次处理的 "CDC Time Slice File", 然后找到下一个 "CDC Time Slice File", 给分布式锁上锁 (用乐观锁的方式上锁) 后开始处理数据并执行 UPSERT. 处理完之后更新 metadata store 中的状态, 释放锁.
        - 这种方式是假设将一个 "CDC Time Slice File" 中的数据写入 Datalake 所需的时间要小于 "CDC Time Slice File" 中的 event time 时间间隔 (在我们这个例子中是 1 分钟). 不然就是处理能力跟不上数据的产生速度了. 需要用分儿治之的方式解决, 这个我们以后再详细讨论.
        - 在真正写入之前, 我们会对 Slice File 中的数据按照 id 来分组, 并只保留每个 id 的最新的一条数据. 这样可以过滤掉一部分不必要的数据. 这个操作一般是在内存中进行的, 因为数据量不大, 所以速度一般很快.
- 3.5 Orchestrator 的调度逻辑如下.
    - 通过跟 metadata store 中被处理过的最新的 "CDC Time Slice File" 的时间跟当前时间做比较, 确定是否有新的 "CDC Time Slice File" 需要处理. 如果有则调度一个 Worker 来处理. 在我们这个例子中, 这个检查频率可以是 10 秒一次.


Stream Partitioning
------------------------------------------------------------------------------
大部分的 Stream 系统都是分布式系统, 它们的底层都是分区的. 一般来说只能保证在分区内的 Record 的产生顺序和消费顺序是一致的, 但是不同分区之间的 Record 的产生顺序和消费顺序是无法保证的. 这里我们通常使用 "id"
 作为 partition key, 确保对于同一条记录的 CDC event 都会落到同一个 partition 中. 这样我们就可以保证同一条记录的 CDC event 的顺序是正确的. 

.. note::

    请注意, 这里的 Partition 是 Stream Partition, 跟 2.2 中的 Data Partition 是完全不同的概念.

既然 Stream 有 Partition, 那么 Consumer 也自然是对应每个 Partition 一个. 那么最终的 "CDC Time Slice File" 也会是每分钟每个 Partition 一个. 例如你的 Stream 有 10 个 Partition, 那么每分钟就会总共生成 10 个 "CDC Time Slice File".

如果某个 Consumer 挂了导致 "CDC Time Slice File" 少于 10 个, 我们可以无视并继续照常运行 CDC Data Pipeline, 因为这个缺失的数据都来自于同一个 Partition, 其他的 Partition 上的数据不可能有这个缺失的 Partition 中的数据相同的 id.


Stream Consumer
------------------------------------------------------------------------------
一般这个 Consumer 在收到数据后会将数据列示存储的方式落盘, 而不是用 CDC event 中的数据格式. 例如 CDC 中的数据可能是 JSON, CSV, XML, 但是为了后续 ETL 处理更快, 我们会将数据转换成 Parquet 格式. 由于 Consumer 收到的数据不需要立刻被后续的 Data Pipeline 所处理, 而是要在一定的时间窗口中聚合后再进行, 所以运行时间是相当的充裕, 数据格式转化所带来的额外开销可以忽略不计.


Write Optimization
------------------------------------------------------------------------------
因为 Stream Partition 的原因, 在同一个 Time Slice 下我们会有多个 Slice File. 而对于写入 Data Lake 的操作来说我们是要将这些数据写到不同的 Data Partition 中的, 所以我们将这些 Slice File 合并后然后按照 Data Partition key 来分成多份交给多个 CPU 来并行写要更高效一些.

但由于在 3.4 中我们提到了, 对于每个 id 我们只保留最新的一条数据, 所以这个 group by 的操作所在的数据集越小越高, 所以我们会对每个 Slice File 先做 id 的 group by, 然后再合并, 然后再根据 Data Partition key 来分成多份.

在各种写入引擎中这种根据 Data Partition key 来分成多份的操作都是很常见的并且会自动执行, 例如 Spark, DeltaLake, Hudi 等有这个功能, 你无需手动将数据按照 Data Partition key 来将数据分成多份.


Backend Agnostic
------------------------------------------------------------------------------
这个 Solution 中的所有组件都有多重选择, 而无需锁定在某个特定的编程语言, 工具, 服务提供商上.

- Database: 大部分 Transaction 数据库 (包括 Transaction NoSQL, DynamoDB, MongoDB 等) 都支持 CDC Stream.
- Stream: 市场上有许多工具都可以用来做 Stream. 例如 Kafka, Pulsar, AWS Kinesis, ...
- CDC Data Persistence Consumer: 你可以用各种 Computational Resource 来消费 Stream 数据. 可以 Lambda Function.
- DataLake and Storage: 你可以用各种 Object Storage 来存储数据. 例如 S3, GCS, Azure Blob Storage, .... 而数据的读写引擎可以选用支持 ACID 以及 Upsert 的 DeltaLake, Hudi, Iceburg 中的一个.
- CDC Data Pipeline Orchestrator: 你可以用各种 Orchestration 工具来调度 CDC Data Pipeline. 例如 Airflow, AWS StepFunction 或者 AWS Lambda Function (因为这个 Orchestrator 非常简单, 本质上就是个 10 秒运行一次的 Cron Job).
- CDC Data Pipeline Worker:
    - Programming Language: 你可以用 Spark + Java/Scala/Python (还有 rust 的工具, 不过一般都是通过 Python binding 来操作, 而不会直接用 rust 来写业务逻辑).
    - Computational Resource: AWS Lambda Function, ECS (容器应用), EMR / Glue (Spark) 等等都可以.
- CDC Data Pipeline Metadata Store: 任何带有持久化的中等性能的 KV Store 都可以. 例如 DynamoDB, Zookeeper, ETCD. 因为 Orchestrator 和 Worker 的执行频率并不高, 所以这个 KV Store 的性能要求并不高.
