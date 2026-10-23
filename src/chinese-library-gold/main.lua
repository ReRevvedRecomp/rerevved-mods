local gold_addition = 1

return
{
    provider_id = 'aeshur.chinese-library-gold',
    rules =
    {
        {
            id = 'chinese-library-fixed-gold',
            kind = 'building_yield',
            civilization = 'china',
            building = 'library',
            yield = 'gold',
            amount = gold_addition,
        },
    },
}
