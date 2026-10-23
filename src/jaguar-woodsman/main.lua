local forest_bonus = 50
local sign = forest_bonus >= 0 and '+' or ''

return
{
    provider_id = 'aeshur.jaguar-woodsman',
    rules =
    {
        {
            id = 'jaguar-warrior-forest-attack',
            kind = 'unit_combat',
            civilization = 'aztec',
            base_unit_type = 'warrior',
            identity = 'jaguar_warrior',
            terrain = 'forest',
            property = 'attack',
            percentage_delta = forest_bonus,
        },
        {
            id = 'jaguar-warrior-forest-defense',
            kind = 'unit_combat',
            civilization = 'aztec',
            base_unit_type = 'warrior',
            identity = 'jaguar_warrior',
            terrain = 'forest',
            property = 'defense',
            percentage_delta = forest_bonus,
        },
        {
            id = 'jaguar-woodsman-text',
            kind = 'nation_select_text',
            surface = 'unique_unit',
            civilization = 'aztec',
            base_unit_type = 'warrior',
            identity = 'jaguar_warrior',
            display_form = 'unit',
            text = 'Jaguar Warrior (' .. sign .. forest_bonus .. '% in Forest)',
        },
    },
}
