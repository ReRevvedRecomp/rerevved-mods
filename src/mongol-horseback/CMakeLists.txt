cmake_minimum_required(VERSION 3.25)
project(mongol_horseback LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(mongol_horseback mod_main.cpp)
if(UNIX)
    target_link_libraries(mongol_horseback PRIVATE ${CMAKE_DL_LIBS})
endif()
