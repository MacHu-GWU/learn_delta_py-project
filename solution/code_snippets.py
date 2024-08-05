# ------------------------------------------------------------------------------
# Data Model
# ------------------------------------------------------------------------------
{
    "id": "id-1",
    "create_time": "2019-01-01T08:30:00.123Z",
    "update_time": "2019-01-01T10:15:00.456Z",
    "...": "..."
}
# ------------------------------------------------------------------------------
# S3 Structure
# ------------------------------------------------------------------------------
s3://bucket/${database_name}/${table_name}/${partition}/${data_file}
s3://bucket/mydatabase/mytable/year=2024/month=03/day=01/1.parquet
s3://bucket/mydatabase/mytable/year=2024/month=03/day=01/2.parquet
s3://bucket/mydatabase/mytable/year=2024/month=03/day=01/3.parquet

{
    "id": "id-1",
    "create_time": "2019-01-01",
    "update_time": "2019-01-06",
    "...": "..."
}
{
    "id": "id-1",
    "create_time": "2019-01-01",
    "update_time": "2019-01-07",
    "...": "..."
}
{
    "id": "id-1",
    "create_time": "2019-01-01",
    "update_time": "2019-01-08",
    "...": "..."
}
