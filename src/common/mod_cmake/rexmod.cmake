# Shared CMake helper for ReRevved code mods.
cmake_minimum_required(VERSION 3.25)

if(NOT TARGET rex::runtime)
    find_package(rexglue 0.10.0 CONFIG REQUIRED)
endif()

function(rexmod_add_plugin target_name)
    add_library(${target_name} SHARED ${ARGN})
    set_target_properties(${target_name} PROPERTIES
        CXX_STANDARD 23
        CXX_STANDARD_REQUIRED ON
        RELWITHDEBINFO_POSTFIX "rd"
        DEBUG_POSTFIX "d"
        RELEASE_POSTFIX ""
    )
    target_link_libraries(${target_name} PRIVATE rex::runtime)
    target_include_directories(${target_name} PRIVATE
        ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../api
    )
endfunction()
