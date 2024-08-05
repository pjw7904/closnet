#ifndef LOGGER_H
#define LOGGER_H

/*
 * Standard library imports.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

/*****************************************
 * CONSTANTS 
 *****************************************/
// None

/*****************************************
 * STRUCTURES 
 *****************************************/
// None

/*****************************************
 * FUNCTION PROTOTYPES 
 *****************************************/
void open_log_file(const char *file_path);
void close_log_file();
void log_message(const char *format, ...);

#endif
