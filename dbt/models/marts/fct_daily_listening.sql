{{ config(materialized='table') }}

with plays as (
    select * from {{ ref('stg_spotify__listening_history') }}
),

daily as (
    select
        date_trunc('day', played_at_utc)::date  as listen_date,
        count(*)                                as tracks_played,
        count(distinct track_id)                as unique_tracks,
        count(distinct album_id)                as unique_albums,
        sum(duration_seconds) / 60.0            as minutes_listened,
        avg(popularity)                         as avg_track_popularity
    from plays
    group by 1
)

select * from daily
order by listen_date
