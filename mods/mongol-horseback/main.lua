return
{
    provider_id = 'aeshur.mongol-horseback',
    rules =
    {
        {
            id = 'mongol-ancient-horseback-riding',
            kind = 'era_technology_ability',
            civilization = 'mongolian',
            unlock_era = 'ancient',
            technology = 'horseback_riding',
        },
        {
            id = 'mongol-ancient-horseback-riding-text',
            kind = 'nation_select_text',
            surface = 'era_ability',
            civilization = 'mongolian',
            unlock_era = 'ancient',
            ability = 'knowledge_of_horseback_riding',
            text = 'Start with Horseback Riding',
        },
    },
}
