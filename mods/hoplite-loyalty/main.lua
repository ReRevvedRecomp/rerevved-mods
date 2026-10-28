local production_delta = -30

return
{
    provider_id = 'aeshur.hoplite-loyalty',
    rules =
    {
        {
            id = 'hoplite-loyalty',
            kind = 'unit_effect',
            civilization = 'greek',
            base_unit_type = 'phalanx',
            identity = 'hoplite',
            effect = 'creation_loyalty',
        },
        {
            id = 'hoplite-production-cost',
            kind = 'unit_production_cost',
            civilization = 'greek',
            base_unit_type = 'phalanx',
            identity = 'hoplite',
            percentage_delta = production_delta,
        },
        {
            id = 'hoplite-loyalty-text',
            kind = 'nation_select_text',
            surface = 'unique_unit',
            civilization = 'greek',
            base_unit_type = 'phalanx',
            identity = 'hoplite',
            display_form = 'unit',
            text = 'Hoplite (Loyalty, 10 Production)',
        },
    },
}
