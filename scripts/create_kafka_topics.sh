#!/bin/bash
# 创建 AM-HK 所需的所有 Kafka Topics

KAFKA_HOME=/home/ubuntu/kafka
BOOTSTRAP=localhost:9092

cd $KAFKA_HOME

# 创建 Topics
echo "Creating Kafka topics..."

bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 6 --replication-factor 1 --topic am-hk-raw-market-data 2>/dev/null || echo "Topic am-hk-raw-market-data already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 4 --replication-factor 1 --topic am-hk-factor-data 2>/dev/null || echo "Topic am-hk-factor-data already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 3 --replication-factor 1 --topic am-hk-signals 2>/dev/null || echo "Topic am-hk-signals already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 2 --replication-factor 1 --topic am-hk-decisions 2>/dev/null || echo "Topic am-hk-decisions already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 2 --replication-factor 1 --topic am-hk-trading-decisions 2>/dev/null || echo "Topic am-hk-trading-decisions already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 2 --replication-factor 1 --topic am-hk-executions 2>/dev/null || echo "Topic am-hk-executions already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 2 --replication-factor 1 --topic am-hk-risk-approved-trades 2>/dev/null || echo "Topic am-hk-risk-approved-trades already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 1 --replication-factor 1 --topic am-hk-agent-commands 2>/dev/null || echo "Topic am-hk-agent-commands already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 1 --replication-factor 1 --topic am-hk-agent-status 2>/dev/null || echo "Topic am-hk-agent-status already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 2 --replication-factor 1 --topic am-hk-feedback 2>/dev/null || echo "Topic am-hk-feedback already exists"
bin/kafka-topics --create --if-not-exists --bootstrap-server $BOOTSTRAP --partitions 1 --replication-factor 1 --topic am-hk-model-updates 2>/dev/null || echo "Topic am-hk-model-updates already exists"

echo "All topics created successfully!"
bin/kafka-topics --list --bootstrap-server $BOOTSTRAP
