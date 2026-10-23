local production_bonus = 1

return
{
    provider_id = 'aeshur.hills-production',
    rules =
    {
        {
            id = 'hills-production',
            kind = 'terrain_yield',
            terrain = 'hill',
            component = 'production',
            operation = 'add',
            value = production_bonus,
        },
    },
}
