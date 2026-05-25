"""Glue job: Spotify Bronze → Silver.

Reads raw JSON from s3://bronze/source=spotify/date=YYYY-MM-DD/,
flattens the recently-played payload into a tabular schema, deduplicates
on (played_at, track_id), and writes Parquet to s3://silver/source=spotify/...

Submitting:
    aws glue start-job-run --job-name spotify-bronze-to-silver \
        --arguments '--RUN_DATE=2026-05-25'
"""

from __future__ import annotations

import sys

from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

args = getResolvedOptions(sys.argv, ["JOB_NAME", "RUN_DATE", "BRONZE_BUCKET", "SILVER_BUCKET"])

sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session

# --- Schema enforcement on read protects against vendor schema drift. ---
recently_played_schema = StructType([
    StructField("items", ArrayType(StructType([
        StructField("played_at", StringType()),
        StructField("track", StructType([
            StructField("id", StringType()),
            StructField("name", StringType()),
            StructField("duration_ms", StringType()),
            StructField("popularity", StringType()),
            StructField("artists", ArrayType(StructType([
                StructField("id", StringType()),
                StructField("name", StringType()),
            ]))),
            StructField("album", StructType([
                StructField("id", StringType()),
                StructField("name", StringType()),
                StructField("release_date", StringType()),
            ])),
        ])),
    ]))),
])

bronze_path = f"s3://{args['BRONZE_BUCKET']}/source=spotify/date={args['RUN_DATE']}/"
silver_path = f"s3://{args['SILVER_BUCKET']}/source=spotify/"

raw = spark.read.schema(recently_played_schema).json(bronze_path)

flat = (
    raw.select(F.explode("items").alias("item"))
       .select(
           F.col("item.played_at").cast(TimestampType()).alias("played_at"),
           F.col("item.track.id").alias("track_id"),
           F.col("item.track.name").alias("track_name"),
           F.col("item.track.duration_ms").cast("long").alias("duration_ms"),
           F.col("item.track.popularity").cast("int").alias("popularity"),
           F.col("item.track.album.id").alias("album_id"),
           F.col("item.track.album.name").alias("album_name"),
           F.col("item.track.album.release_date").alias("album_release_date"),
           F.col("item.track.artists").alias("artists"),
       )
       .dropDuplicates(["played_at", "track_id"])
       .withColumn("year", F.year("played_at"))
       .withColumn("month", F.month("played_at"))
       .withColumn("day", F.dayofmonth("played_at"))
)

(
    flat.write
        .mode("append")
        .partitionBy("year", "month", "day")
        .parquet(silver_path)
)
