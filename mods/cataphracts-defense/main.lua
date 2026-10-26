local defense_bonus = 1
local sign = defense_bonus >= 0 and '+' or ''

return
{
    provider_id = 'aeshur.cataphracts-defense',
    rules =
    {
        {
            id = 'cataphract-defense',
            kind = 'unique_unit_scalar',
            civilization = 'roman',
            base_unit_type = 'knights',
            identity = 'cataphract',
            property = 'base_defense',
            operation = 'add',
            value = defense_bonus,
        },
        {
            id = 'cataphract-defense-text',
            kind = 'nation_select_text',
            surface = 'unique_unit',
            civilization = 'roman',
            base_unit_type = 'knights',
            identity = 'cataphract',
            display_form = 'unit',
            text = 'Cataphract (' .. sign .. defense_bonus .. ' Defense)',
        },
    },
}
