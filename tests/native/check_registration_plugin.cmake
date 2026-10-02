execute_process(
    COMMAND "${HOST}" "${KIND}" "${MODE}" "${PLUGIN}"
    RESULT_VARIABLE result
    OUTPUT_VARIABLE expected_diagnostic
    ERROR_VARIABLE diagnostic
)
if(NOT result STREQUAL "0")
    message(FATAL_ERROR "Registration host failed (${result}): ${diagnostic}")
endif()
if(NOT diagnostic STREQUAL expected_diagnostic)
    message(FATAL_ERROR "Expected diagnostic [${expected_diagnostic}], received [${diagnostic}]")
endif()
