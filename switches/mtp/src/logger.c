#include "logger.h"

static FILE *log_file = NULL;

void open_log_file(const char *file_path) 
{
    log_file = fopen(file_path, "a");

    if(log_file == NULL)
    {
        perror("Failed to open log file");
        exit(EXIT_FAILURE);
    }
}

void close_log_file() 
{
    if(log_file != NULL) 
    {
        fclose(log_file);
        log_file = NULL;
    }
}

void log_message(const char *format, ...) 
{
    va_list args;
    va_start(args, format);

    if(log_file != NULL)
    {
        vfprintf(log_file, format, args);
        fflush(log_file);
    }

    va_end(args);
}
