cmake_minimum_required(VERSION 3.25)
project(chinese_library_gold LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(chinese_library_gold mod_main.cpp)

if(UNIX)
    target_link_libraries(chinese_library_gold PRIVATE ${CMAKE_DL_LIBS})
endif()
