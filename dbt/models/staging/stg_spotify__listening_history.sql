{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'spotify_listening_history') }}
),

renamed as (
    select
        played_at                         as played_at_utc,
        track_id,
        track_name,
        duration_ms / 1000.0              as duration_seconds,
        popularity,
        album_id,
        album_name,
        try_to_date(album_release_date)   as album_released_on,
        artists
    from source
)

select * from renamed
