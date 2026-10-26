local movement_bonus = 1
local sign = movement_bonus >= 0 and '+' or ''

return
{
    provider_id = 'aeshur.keshik-movement',
    rules =
    {
        {
            id = 'keshik-movement',
            kind = 'unit_movement',
            civilization = 'mongolian',
            base_unit_type = 'horsemen',
            identity = 'keshik',
            value = movement_bonus,
        },
        {
            id = 'keshik-movement-text',
            kind = 'nation_select_text',
            surface = 'unique_unit',
            civilization = 'mongolian',
            base_unit_type = 'horsemen',
            identity = 'keshik',
            display_form = 'unit',
            text = 'Keshik (' .. sign .. movement_bonus .. ' Movement)',
        },
    },
}
