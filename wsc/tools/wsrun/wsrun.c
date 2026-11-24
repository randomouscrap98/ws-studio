/*
 * wsrun - run a WonderSwan Color ROM in a libretro core for a fixed number
 * of frames and save the final frame and system RAM.
 *
 * The core must be a beetle-wswan build (224x144, XRGB8888 or RGB565).
 */
#include <ctype.h>
#include <dlfcn.h>
#include <errno.h>
#include <limits.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

#include "libretro.h"

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

#ifndef WSRUN_BUILD_DIR
#define WSRUN_BUILD_DIR "wsc/build"
#endif

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

struct core_api {
    void (*set_environment)(retro_environment_t);
    void (*set_video_refresh)(retro_video_refresh_t);
    void (*set_audio_sample)(retro_audio_sample_t);
    void (*set_audio_sample_batch)(retro_audio_sample_batch_t);
    void (*set_input_poll)(retro_input_poll_t);
    void (*set_input_state)(retro_input_state_t);
    void (*init)(void);
    void (*deinit)(void);
    void (*run)(void);
    bool (*load_game)(const struct retro_game_info *);
    void (*unload_game)(void);
    void *(*get_memory_data)(unsigned);
    size_t (*get_memory_size)(unsigned);
};

#define MAX_MARKERS 16

struct marker {
    uint32_t address;
    unsigned width;
    uint32_t value;
};

struct options {
    const char *core;
    const char *rom;
    const char *input;
    const char *png;
    const char *raw;
    const char *ram;
    uint32_t frames;
    bool have_frames;
    struct marker markers[MAX_MARKERS];
    unsigned marker_count;
    uint32_t marker_timeout;
    bool have_marker;
    int boot_id;
    uint32_t tick_address;
    unsigned tick_width;
    bool have_tick;
    uint32_t max_ticks;
    bool have_max_ticks;
    const char *trace;
    bool input_tick;
};

struct input_event {
    uint32_t frame;
    uint32_t mask;
    unsigned line;
};

static struct core_api core;
static enum retro_pixel_format pixel_format = RETRO_PIXEL_FORMAT_UNKNOWN;
static char system_dir[PATH_MAX];
static char save_dir[PATH_MAX];

static uint8_t *frame_rgb;
static size_t frame_rgb_cap;
static unsigned frame_width;
static unsigned frame_height;
static bool have_frame;
static bool video_error;
static char video_error_message[256];

static struct input_event *input_events;
static size_t input_event_count;
static size_t input_event_cap;
static uint32_t input_mask;

static void core_log(enum retro_log_level level, const char *fmt, ...)
{
    va_list ap;

    (void)level;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
}

static bool environment_cb(unsigned cmd, void *data)
{
    switch (cmd) {
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT: {
        enum retro_pixel_format fmt = *(const enum retro_pixel_format *)data;

        if (fmt == RETRO_PIXEL_FORMAT_XRGB8888 ||
            fmt == RETRO_PIXEL_FORMAT_RGB565) {
            pixel_format = fmt;
            return true;
        }
        return false;
    }
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
        *(const char **)data = system_dir;
        return true;
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
        *(const char **)data = save_dir;
        return true;
    case RETRO_ENVIRONMENT_GET_LOG_INTERFACE:
        ((struct retro_log_callback *)data)->log = core_log;
        return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE:
        /* Not set: the core keeps its built-in option defaults. */
        return false;
    default:
        return false;
    }
}

static void set_video_error(const char *fmt, ...)
{
    va_list ap;

    if (video_error)
        return;
    video_error = true;
    va_start(ap, fmt);
    vsnprintf(video_error_message, sizeof(video_error_message), fmt, ap);
    va_end(ap);
}

static void video_cb(const void *data, unsigned width, unsigned height,
                     size_t pitch)
{
    size_t bpp;
    size_t need;
    uint8_t *grown;
    unsigned x;
    unsigned y;

    if (!data)
        return; /* NULL means "repeat the previous frame". */

    if (pixel_format == RETRO_PIXEL_FORMAT_XRGB8888)
        bpp = 4;
    else if (pixel_format == RETRO_PIXEL_FORMAT_RGB565)
        bpp = 2;
    else {
        set_video_error("video frame arrived before a supported pixel format "
                        "was chosen");
        return;
    }

    if (width == 0 || height == 0) {
        set_video_error("core reported an empty frame");
        return;
    }
    if (pitch < (size_t)width * bpp) {
        set_video_error("core pitch %zu is smaller than a %ux%u row (%zu "
                        "bytes)", pitch, width, height, (size_t)width * bpp);
        return;
    }

    need = (size_t)width * height * 3;
    if (need > frame_rgb_cap) {
        grown = realloc(frame_rgb, need);
        if (!grown) {
            set_video_error("out of memory for the %ux%u RGB frame", width,
                            height);
            return;
        }
        frame_rgb = grown;
        frame_rgb_cap = need;
    }

    for (y = 0; y < height; y++) {
        const uint8_t *row = (const uint8_t *)data + y * pitch;
        uint8_t *dst = frame_rgb + (size_t)y * width * 3;

        for (x = 0; x < width; x++) {
            if (pixel_format == RETRO_PIXEL_FORMAT_XRGB8888) {
                uint32_t px;

                memcpy(&px, row + (size_t)x * 4, sizeof(px));
                dst[x * 3 + 0] = (uint8_t)(px >> 16);
                dst[x * 3 + 1] = (uint8_t)(px >> 8);
                dst[x * 3 + 2] = (uint8_t)px;
            } else {
                uint16_t px;
                unsigned r;
                unsigned g;
                unsigned b;

                memcpy(&px, row + (size_t)x * 2, sizeof(px));
                r = (px >> 11) & 0x1f;
                g = (px >> 5) & 0x3f;
                b = px & 0x1f;
                dst[x * 3 + 0] = (uint8_t)((r << 3) | (r >> 2));
                dst[x * 3 + 1] = (uint8_t)((g << 2) | (g >> 4));
                dst[x * 3 + 2] = (uint8_t)((b << 3) | (b >> 2));
            }
        }
    }

    frame_width = width;
    frame_height = height;
    have_frame = true;
}

static void audio_sample_cb(int16_t left, int16_t right)
{
    (void)left;
    (void)right;
}

static size_t audio_sample_batch_cb(const int16_t *data, size_t frames)
{
    (void)data;
    return frames;
}

static void input_poll_cb(void)
{
}

static int16_t input_state_cb(unsigned port, unsigned device, unsigned index,
                              unsigned id)
{
    if (port != 0 || device != RETRO_DEVICE_JOYPAD || index != 0)
        return 0;

    if (id == RETRO_DEVICE_ID_JOYPAD_MASK)
        return (int16_t)(input_mask & 0xffff);
    if (id >= 32)
        return 0;
    return (int16_t)((input_mask >> id) & 1);
}

static bool parse_u32_base(const char *text, int base, uint32_t *out)
{
    char *end;
    unsigned long value;

    errno = 0;
    value = strtoul(text, &end, base);
    if (errno != 0 || end == text || *end != '\0' || value > UINT32_MAX)
        return false;
    *out = (uint32_t)value;
    return true;
}

static bool parse_u32(const char *text, uint32_t *out)
{
    return parse_u32_base(text, 10, out);
}

/* ADDR:SIZE, both in C notation. */
static bool parse_address_size(const char *text, uint32_t *address,
                               unsigned *width)
{
    char *copy;
    char *sep;
    uint32_t addr;
    uint32_t size;
    bool ok = false;

    copy = strdup(text);
    if (!copy)
        return false;
    sep = strchr(copy, ':');
    if (!sep)
        goto done;
    *sep++ = '\0';
    if (!parse_u32_base(copy, 0, &addr) || !parse_u32(sep, &size))
        goto done;
    if (size != 1 && size != 2 && size != 4)
        goto done;
    *address = addr;
    *width = (unsigned)size;
    ok = true;
done:
    free(copy);
    return ok;
}

/* ADDR:SIZE:VALUE, all in C notation (0x... or decimal). */
static bool parse_marker(const char *text, struct options *opts)
{
    char *copy;
    char *first;
    char *second;
    uint32_t address;
    uint32_t width;
    uint32_t value;
    bool ok = false;

    copy = strdup(text);
    if (!copy)
        return false;
    first = strchr(copy, ':');
    if (!first)
        goto done;
    *first++ = '\0';
    second = strchr(first, ':');
    if (!second)
        goto done;
    *second++ = '\0';
    if (!parse_u32_base(copy, 0, &address) ||
        !parse_u32(first, &width) ||
        !parse_u32_base(second, 0, &value))
        goto done;
    if (width != 1 && width != 2 && width != 4)
        goto done;
    if (opts->marker_count == MAX_MARKERS)
        goto done;
    opts->markers[opts->marker_count].address = address;
    opts->markers[opts->marker_count].width = (unsigned)width;
    opts->markers[opts->marker_count].value = value;
    opts->marker_count++;
    opts->have_marker = true;
    ok = true;
done:
    free(copy);
    return ok;
}

static char *trim(char *text)
{
    char *end;

    while (*text && isspace((unsigned char)*text))
        text++;
    end = text + strlen(text);
    while (end > text && isspace((unsigned char)end[-1]))
        *--end = '\0';
    return text;
}

static bool button_id(const char *name, unsigned *id)
{
    /* beetle-wswan's horizontal-layout table (update_input(), map[0]). */
    static const struct {
        const char *name;
        unsigned id;
    } buttons[] = {
        { "X1", RETRO_DEVICE_ID_JOYPAD_UP },
        { "X2", RETRO_DEVICE_ID_JOYPAD_RIGHT },
        { "X3", RETRO_DEVICE_ID_JOYPAD_DOWN },
        { "X4", RETRO_DEVICE_ID_JOYPAD_LEFT },
        { "Y1", RETRO_DEVICE_ID_JOYPAD_R2 },
        { "Y2", RETRO_DEVICE_ID_JOYPAD_R },
        { "Y3", RETRO_DEVICE_ID_JOYPAD_L2 },
        { "Y4", RETRO_DEVICE_ID_JOYPAD_L },
        { "A", RETRO_DEVICE_ID_JOYPAD_A },
        { "B", RETRO_DEVICE_ID_JOYPAD_B },
        { "START", RETRO_DEVICE_ID_JOYPAD_START },
    };
    size_t i;

    for (i = 0; i < sizeof(buttons) / sizeof(buttons[0]); i++) {
        if (strcmp(name, buttons[i].name) == 0) {
            *id = buttons[i].id;
            return true;
        }
    }
    return false;
}

static bool push_input_event(uint32_t frame, uint32_t mask, unsigned line,
                             char *err, size_t err_size)
{
    struct input_event *grown;
    size_t new_cap;

    if (input_event_count == input_event_cap) {
        new_cap = input_event_cap ? input_event_cap * 2 : 16;
        grown = realloc(input_events, new_cap * sizeof(*grown));
        if (!grown) {
            snprintf(err, err_size, "out of memory reading the input file");
            return false;
        }
        input_events = grown;
        input_event_cap = new_cap;
    }

    input_events[input_event_count].frame = frame;
    input_events[input_event_count].mask = mask;
    input_events[input_event_count].line = line;
    input_event_count++;
    return true;
}

static int compare_input_events(const void *a, const void *b)
{
    const struct input_event *ea = a;
    const struct input_event *eb = b;

    if (ea->frame < eb->frame)
        return -1;
    if (ea->frame > eb->frame)
        return 1;
    return 0;
}

static bool parse_input_file(const char *path, char *err, size_t err_size)
{
    FILE *file;
    char *line = NULL;
    size_t line_cap = 0;
    ssize_t line_len;
    unsigned line_number = 0;
    bool ok = true;

    file = fopen(path, "r");
    if (!file) {
        snprintf(err, err_size, "cannot open input file '%s': %s", path,
                 strerror(errno));
        return false;
    }

    while ((line_len = getline(&line, &line_cap, file)) != -1) {
        char *comment;
        char *text;
        char *frame_end;
        char *rest;
        char *save = NULL;
        char *token;
        uint32_t frame;
        uint32_t mask = 0;
        unsigned tokens = 0;
        unsigned none_tokens = 0;

        (void)line_len;
        line_number++;

        comment = strchr(line, '#');
        if (comment)
            *comment = '\0';
        text = trim(line);
        if (*text == '\0')
            continue;

        frame_end = text;
        while (*frame_end && !isspace((unsigned char)*frame_end))
            frame_end++;

        if (*frame_end == '\0') {
            snprintf(err, err_size, "line %u: missing button list",
                     line_number);
            ok = false;
            break;
        }
        *frame_end = '\0';
        rest = trim(frame_end + 1);

        if (!parse_u32(text, &frame)) {
            snprintf(err, err_size, "line %u: bad frame number '%s'",
                     line_number, text);
            ok = false;
            break;
        }
        if (*rest == '\0') {
            snprintf(err, err_size, "line %u: missing button list (use '-' "
                     "for none)", line_number);
            ok = false;
            break;
        }

        for (token = strtok_r(rest, ",", &save); token;
             token = strtok_r(NULL, ",", &save)) {
            unsigned id;

            token = trim(token);
            if (*token == '\0') {
                snprintf(err, err_size, "line %u: empty button name",
                         line_number);
                ok = false;
                break;
            }
            tokens++;
            if (strcmp(token, "-") == 0) {
                none_tokens++;
                continue;
            }
            if (!button_id(token, &id)) {
                snprintf(err, err_size, "line %u: unknown button '%s'",
                         line_number, token);
                ok = false;
                break;
            }
            mask |= 1u << id;
        }
        if (!ok)
            break;

        if (tokens == 0) {
            snprintf(err, err_size, "line %u: missing button list", line_number);
            ok = false;
            break;
        }
        if (none_tokens != 0 && tokens != 1) {
            snprintf(err, err_size, "line %u: '-' cannot be combined with "
                     "other buttons", line_number);
            ok = false;
            break;
        }
        if (none_tokens != 0)
            mask = 0;

        if (!push_input_event(frame, mask, line_number, err, err_size)) {
            ok = false;
            break;
        }
    }

    if (ok && ferror(file)) {
        snprintf(err, err_size, "error reading input file '%s'", path);
        ok = false;
    }
    if (fclose(file) != 0 && ok) {
        snprintf(err, err_size, "error closing input file '%s': %s", path,
                 strerror(errno));
        ok = false;
    }
    free(line);

    if (!ok)
        return false;

    if (input_event_count > 1)
        qsort(input_events, input_event_count, sizeof(*input_events),
              compare_input_events);
    for (size_t i = 1; i < input_event_count; i++) {
        if (input_events[i].frame == input_events[i - 1].frame) {
            snprintf(err, err_size, "lines %u and %u both set frame %u",
                     input_events[i - 1].line, input_events[i].line,
                     input_events[i].frame);
            return false;
        }
    }
    return true;
}

static uint32_t mask_for_frame(uint32_t frame)
{
    uint32_t mask = 0;
    size_t i;

    for (i = 0; i < input_event_count; i++) {
        if (input_events[i].frame > frame)
            break;
        mask = input_events[i].mask;
    }
    return mask;
}

static bool read_file(const char *path, uint8_t **out_data, size_t *out_size)
{
    FILE *file;
    uint8_t *data = NULL;
    long length;
    size_t size;
    bool ok = false;

    file = fopen(path, "rb");
    if (!file) {
        fprintf(stderr, "error: cannot open ROM '%s': %s\n", path,
                strerror(errno));
        return false;
    }

    if (fseek(file, 0, SEEK_END) != 0) {
        fprintf(stderr, "error: cannot seek in '%s': %s\n", path,
                strerror(errno));
        goto done;
    }
    length = ftell(file);
    if (length < 0) {
        fprintf(stderr, "error: cannot get size of '%s': %s\n", path,
                strerror(errno));
        goto done;
    }
    if (fseek(file, 0, SEEK_SET) != 0) {
        fprintf(stderr, "error: cannot rewind '%s': %s\n", path,
                strerror(errno));
        goto done;
    }

    size = (size_t)length;
    data = malloc(size ? size : 1);
    if (!data) {
        fprintf(stderr, "error: out of memory reading '%s'\n", path);
        goto done;
    }
    if (size != 0 && fread(data, 1, size, file) != size) {
        fprintf(stderr, "error: short read from '%s'\n", path);
        goto done;
    }
    if (fclose(file) != 0) {
        file = NULL;
        fprintf(stderr, "error: cannot close '%s': %s\n", path,
                strerror(errno));
        goto done;
    }
    file = NULL;

    *out_data = data;
    *out_size = size;
    data = NULL;
    ok = true;

done:
    if (file && fclose(file) != 0)
        fprintf(stderr, "error: cannot close '%s': %s\n", path,
                strerror(errno));
    free(data);
    return ok;
}

static bool write_file(const char *path, const void *data, size_t size)
{
    FILE *file;
    bool ok = true;

    file = fopen(path, "wb");
    if (!file) {
        fprintf(stderr, "error: cannot create '%s': %s\n", path,
                strerror(errno));
        return false;
    }
    if (size != 0 && fwrite(data, 1, size, file) != size) {
        fprintf(stderr, "error: short write to '%s'\n", path);
        ok = false;
    }
    if (fclose(file) != 0) {
        fprintf(stderr, "error: cannot close '%s': %s\n", path,
                strerror(errno));
        ok = false;
    }
    return ok;
}

static bool write_bytes(FILE *file, const void *data, size_t size)
{
    return size == 0 || fwrite(data, 1, size, file) == size;
}

static bool write_u32(FILE *file, uint32_t value)
{
    uint8_t bytes[4];

    bytes[0] = (uint8_t)value;
    bytes[1] = (uint8_t)(value >> 8);
    bytes[2] = (uint8_t)(value >> 16);
    bytes[3] = (uint8_t)(value >> 24);
    return write_bytes(file, bytes, sizeof(bytes));
}

static bool ensure_dir(const char *path)
{
    struct stat st;

    if (mkdir(path, 0777) == 0)
        return true;
    if (errno != EEXIST) {
        fprintf(stderr, "error: cannot create directory '%s': %s\n", path,
                strerror(errno));
        return false;
    }
    if (stat(path, &st) != 0 || !S_ISDIR(st.st_mode)) {
        fprintf(stderr, "error: '%s' exists but is not a directory\n", path);
        return false;
    }
    return true;
}

static bool init_directories(void)
{
    int n;

    n = snprintf(system_dir, sizeof(system_dir), "%s/wsrun-system",
                 WSRUN_BUILD_DIR);
    if (n < 0 || (size_t)n >= sizeof(system_dir)) {
        fprintf(stderr, "error: system directory path is too long\n");
        return false;
    }
    n = snprintf(save_dir, sizeof(save_dir), "%s/wsrun-save",
                 WSRUN_BUILD_DIR);
    if (n < 0 || (size_t)n >= sizeof(save_dir)) {
        fprintf(stderr, "error: save directory path is too long\n");
        return false;
    }

    return ensure_dir(system_dir) && ensure_dir(save_dir);
}

static void usage(FILE *stream)
{
    fprintf(stream,
            "usage: wsrun --core SO --rom ROM --frames N [--input FILE] "
            "[--png OUT] [--raw OUT] [--ram OUT]\n"
            "             [--marker ADDR:SIZE:VALUE [--marker-timeout N]] "
            "[--boot-id N]\n"
            "             [--tick ADDR:SIZE [--trace OUT] [--max-ticks N] "
            "[--input-tick]]\n");
}

/* The gamerom image carries this marker next to a one-byte boot-scene id.
 * Patching the loaded ROM image survives the CRT's IRAM initialisation,
 * unlike a poke into system RAM before the first frame. */
static const uint8_t boot_magic[] = { 'W', 'S', 'C', 'B', 'O', 'O', 'T' };

static bool patch_boot_id(uint8_t *rom, size_t size, unsigned id)
{
    size_t matches = 0;
    size_t offset = 0;
    size_t i;

    if (id == 0)
        return true;
    while (offset + sizeof(boot_magic) < size) {
        bool same = true;

        for (i = 0; i < sizeof(boot_magic); i++) {
            if (rom[offset + i] != boot_magic[i]) {
                same = false;
                break;
            }
        }
        if (same) {
            matches++;
            rom[offset + sizeof(boot_magic)] = (uint8_t)id;
        }
        offset++;
    }
    if (matches != 1) {
        fprintf(stderr,
                "error: ROM has %zu boot-id slots (expected exactly 1)\n",
                matches);
        return false;
    }
    return true;
}

static bool ram_value(const uint8_t *ram, size_t ram_size, uint32_t address,
                      unsigned width, uint32_t *out)
{
    uint32_t value = 0;
    unsigned i;

    if ((uint64_t)address + width > ram_size)
        return false;
    for (i = 0; i < width; i++)
        value |= (uint32_t)ram[address + i] << (8 * i);
    *out = value;
    return true;
}

static void *load_symbol(void *handle, const char *name)
{
    return dlsym(handle, name);
}

#define RESOLVE(field, name)                                                   \
    do {                                                                       \
        *(void **)(&core.field) = load_symbol(handle, name);                   \
        if (!core.field) {                                                     \
            fprintf(stderr, "error: core is missing symbol %s: %s\n", name,    \
                    dlerror());                                                \
            goto cleanup;                                                      \
        }                                                                      \
    } while (0)

int main(int argc, char **argv)
{
    struct options opts = { 0 };
    struct retro_game_info game_info;
    uint8_t *rom_data = NULL;
    size_t rom_size = 0;
    void *handle = NULL;
    void *ram_data;
    size_t ram_size;
    bool did_init = false;
    bool did_load = false;
    bool ok = false;
    char err[256];
    uint32_t i;
    uint32_t marker_frame = 0;
    int rc = 1;

    opts.boot_id = -1;

    for (i = 1; i < (uint32_t)argc; i++) {
        const char *arg = argv[i];

        if (strcmp(arg, "--help") == 0) {
            usage(stdout);
            return 0;
        } else if (strcmp(arg, "--core") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            opts.core = argv[i];
        } else if (strcmp(arg, "--rom") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            opts.rom = argv[i];
        } else if (strcmp(arg, "--frames") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            if (!parse_u32(argv[i], &opts.frames)) {
                fprintf(stderr, "error: invalid frame count '%s'\n", argv[i]);
                usage(stderr);
                return 2;
            }
            opts.have_frames = true;
        } else if (strcmp(arg, "--marker") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            if (!parse_marker(argv[i], &opts)) {
                fprintf(stderr, "error: invalid marker '%s' "
                        "(expected ADDR:SIZE:VALUE)\n", argv[i]);
                usage(stderr);
                return 2;
            }
        } else if (strcmp(arg, "--marker-timeout") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            if (!parse_u32(argv[i], &opts.marker_timeout)) {
                fprintf(stderr, "error: invalid marker timeout '%s'\n",
                        argv[i]);
                usage(stderr);
                return 2;
            }
        } else if (strcmp(arg, "--boot-id") == 0) {
            uint32_t id;

            if (++i >= (uint32_t)argc)
                goto bad_args;
            if (!parse_u32(argv[i], &id) || id > 255) {
                fprintf(stderr, "error: invalid boot id '%s'\n", argv[i]);
                usage(stderr);
                return 2;
            }
            opts.boot_id = (int)id;
        } else if (strcmp(arg, "--input") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            opts.input = argv[i];
        } else if (strcmp(arg, "--png") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            opts.png = argv[i];
        } else if (strcmp(arg, "--raw") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            opts.raw = argv[i];
        } else if (strcmp(arg, "--ram") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            opts.ram = argv[i];
        } else if (strcmp(arg, "--tick") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            if (!parse_address_size(argv[i], &opts.tick_address,
                                    &opts.tick_width)) {
                fprintf(stderr, "error: invalid tick address '%s' "
                        "(expected ADDR:SIZE)\n", argv[i]);
                usage(stderr);
                return 2;
            }
            opts.have_tick = true;
        } else if (strcmp(arg, "--max-ticks") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            if (!parse_u32(argv[i], &opts.max_ticks)) {
                fprintf(stderr, "error: invalid max tick count '%s'\n",
                        argv[i]);
                usage(stderr);
                return 2;
            }
            opts.have_max_ticks = true;
        } else if (strcmp(arg, "--trace") == 0) {
            if (++i >= (uint32_t)argc)
                goto bad_args;
            opts.trace = argv[i];
        } else if (strcmp(arg, "--input-tick") == 0) {
            opts.input_tick = true;
        } else {
            fprintf(stderr, "error: unknown argument '%s'\n", arg);
            usage(stderr);
            return 2;
        }
    }

    if (!opts.core || !opts.rom || !opts.have_frames) {
bad_args:
        fprintf(stderr, "error: --core, --rom and --frames are required\n");
        usage(stderr);
        return 2;
    }
    if (opts.marker_timeout == 0)
        opts.marker_timeout = 600;
    if (!opts.have_marker && opts.marker_timeout != 600) {
        fprintf(stderr, "error: --marker-timeout requires --marker\n");
        return 2;
    }
    if (!opts.have_tick &&
        (opts.trace || opts.have_max_ticks || opts.input_tick)) {
        fprintf(stderr, "error: --trace, --max-ticks and --input-tick "
                "require --tick\n");
        return 2;
    }
    if (opts.input_tick && !opts.input) {
        fprintf(stderr, "error: --input-tick requires --input\n");
        return 2;
    }

    if (opts.input) {
        if (!parse_input_file(opts.input, err, sizeof(err))) {
            fprintf(stderr, "error: %s\n", err);
            return 1;
        }
    }

    if (!read_file(opts.rom, &rom_data, &rom_size))
        return 1;
    if (opts.boot_id >= 0 &&
        !patch_boot_id(rom_data, rom_size, (unsigned)opts.boot_id))
        goto cleanup;

    if (!init_directories())
        goto cleanup;

    handle = dlopen(opts.core, RTLD_NOW | RTLD_LOCAL);
    if (!handle) {
        fprintf(stderr, "error: cannot load core '%s': %s\n", opts.core,
                dlerror());
        goto cleanup;
    }

    RESOLVE(set_environment, "retro_set_environment");
    RESOLVE(set_video_refresh, "retro_set_video_refresh");
    RESOLVE(set_audio_sample, "retro_set_audio_sample");
    RESOLVE(set_audio_sample_batch, "retro_set_audio_sample_batch");
    RESOLVE(set_input_poll, "retro_set_input_poll");
    RESOLVE(set_input_state, "retro_set_input_state");
    RESOLVE(init, "retro_init");
    RESOLVE(deinit, "retro_deinit");
    RESOLVE(run, "retro_run");
    RESOLVE(load_game, "retro_load_game");
    RESOLVE(unload_game, "retro_unload_game");
    RESOLVE(get_memory_data, "retro_get_memory_data");
    RESOLVE(get_memory_size, "retro_get_memory_size");

    core.set_environment(environment_cb);
    core.init();
    did_init = true;

    core.set_video_refresh(video_cb);
    core.set_audio_sample(audio_sample_cb);
    core.set_audio_sample_batch(audio_sample_batch_cb);
    core.set_input_poll(input_poll_cb);
    core.set_input_state(input_state_cb);

    memset(&game_info, 0, sizeof(game_info));
    game_info.path = opts.rom;
    game_info.data = rom_data;
    game_info.size = rom_size;
    game_info.meta = NULL;

    if (!core.load_game(&game_info)) {
        fprintf(stderr, "error: core refused ROM '%s'\n", opts.rom);
        goto cleanup;
    }
    did_load = true;

    /* Some cores pick their pixel format in retro_init, others in
     * retro_load_game. */
    if (pixel_format == RETRO_PIXEL_FORMAT_UNKNOWN) {
        fprintf(stderr, "error: core did not choose XRGB8888 or RGB565\n");
        goto cleanup;
    }

    ram_data = core.get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
    ram_size = core.get_memory_size(RETRO_MEMORY_SYSTEM_RAM);

    if (opts.have_marker) {
        bool found = false;

        if (!ram_data || ram_size == 0) {
            fprintf(stderr, "error: core did not expose system RAM\n");
            goto cleanup;
        }
        for (i = 0; i < opts.marker_timeout; i++) {
            bool all_match = true;
            unsigned j;

            input_mask = 0;
            core.run();
            if (video_error) {
                fprintf(stderr, "error: %s\n", video_error_message);
                goto cleanup;
            }
            for (j = 0; j < opts.marker_count; j++) {
                uint32_t value;

                if (!ram_value(ram_data, ram_size,
                               opts.markers[j].address,
                               opts.markers[j].width, &value)) {
                    fprintf(stderr,
                            "error: marker address 0x%X is outside the "
                            "%zu-byte RAM dump\n",
                            opts.markers[j].address, ram_size);
                    goto cleanup;
                }
                if (value != opts.markers[j].value)
                    all_match = false;
            }
            if (all_match) {
                marker_frame = i;
                found = true;
                break;
            }
        }
        if (!found) {
            fprintf(stderr,
                    "error: markers were not reached in %u frames\n",
                    opts.marker_timeout);
            goto cleanup;
        }
    }

    /* Input frame numbers are relative to the marker when one is used. */
    if (opts.have_tick) {
        uint32_t previous;
        uint32_t logical_ticks = 0;
        FILE *trace = NULL;

        if (!ram_data || ram_size == 0) {
            fprintf(stderr, "error: core did not expose system RAM\n");
            goto cleanup;
        }
        if (!ram_value(ram_data, ram_size, opts.tick_address,
                       opts.tick_width, &previous)) {
            fprintf(stderr,
                    "error: tick address 0x%X is outside the %zu-byte RAM "
                    "dump\n", opts.tick_address, ram_size);
            goto cleanup;
        }

        if (opts.trace) {
            static const char magic[8] = { 'G', 'B', 'O', 'T', 'R', 'A', 'C',
                                           'E' };

            trace = fopen(opts.trace, "wb");
            if (!trace) {
                fprintf(stderr, "error: cannot create '%s': %s\n",
                        opts.trace, strerror(errno));
                goto cleanup;
            }
            if (!write_bytes(trace, magic, sizeof(magic)) ||
                !write_u32(trace, 1) || !write_u32(trace, opts.tick_width) ||
                !write_u32(trace, (uint32_t)ram_size)) {
                fprintf(stderr, "error: cannot write trace header\n");
                goto cleanup;
            }
        }

        for (i = 0; i < opts.frames; i++) {
            uint32_t value;

            if (opts.input_tick)
                input_mask = mask_for_frame(logical_ticks + 1);
            else
                input_mask = mask_for_frame(i);
            core.run();
            if (video_error) {
                fprintf(stderr, "error: %s\n", video_error_message);
                goto cleanup;
            }
            if (!ram_value(ram_data, ram_size, opts.tick_address,
                           opts.tick_width, &value)) {
                fprintf(stderr, "error: tick address left the RAM dump\n");
                goto cleanup;
            }
            if (value == previous)
                continue;

            previous = value;
            logical_ticks++;
            if (trace &&
                (!write_u32(trace, logical_ticks) ||
                 !write_u32(trace, (uint32_t)ram_size) ||
                 !write_bytes(trace, ram_data, ram_size))) {
                fprintf(stderr, "error: cannot write trace record\n");
                goto cleanup;
            }
            if (opts.have_max_ticks && logical_ticks >= opts.max_ticks)
                break;
        }

        if (trace && fclose(trace) != 0) {
            trace = NULL;
            fprintf(stderr, "error: cannot close trace file: %s\n",
                    strerror(errno));
            goto cleanup;
        }
        if (printf(" ticks=%u\n", logical_ticks) < 0 || fflush(stdout) != 0) {
            fprintf(stderr, "error: cannot write to stdout\n");
            goto cleanup;
        }
    } else {
        for (i = 0; i < opts.frames; i++) {
            input_mask = mask_for_frame(i);
            core.run();
            if (video_error) {
                fprintf(stderr, "error: %s\n", video_error_message);
                goto cleanup;
            }
        }
    }

    if ((opts.raw || opts.png) && !have_frame) {
        fprintf(stderr, "error: no video frame was produced\n");
        goto cleanup;
    }

    if (opts.raw) {
        if (!write_file(opts.raw, frame_rgb,
                        (size_t)frame_width * frame_height * 3))
            goto cleanup;
    }
    if (opts.png) {
        if (!stbi_write_png(opts.png, (int)frame_width, (int)frame_height, 3,
                            frame_rgb, (int)((size_t)frame_width * 3))) {
            fprintf(stderr, "error: cannot write PNG '%s'\n", opts.png);
            goto cleanup;
        }
    }
    if (opts.ram) {
        if (!ram_data || ram_size == 0) {
            fprintf(stderr, "error: core did not expose system RAM\n");
            goto cleanup;
        }
        if (!write_file(opts.ram, ram_data, ram_size))
            goto cleanup;
    }

    if (printf("frames=%u width=%u height=%u ram_size=%zu", opts.frames,
               have_frame ? frame_width : 0,
               have_frame ? frame_height : 0, ram_size) < 0 ||
        (opts.have_marker && printf(" marker_frame=%u", marker_frame) < 0) ||
        printf("\n") < 0 || fflush(stdout) != 0) {
        fprintf(stderr, "error: cannot write to stdout\n");
        goto cleanup;
    }

    ok = true;

cleanup:
    if (did_load)
        core.unload_game();
    if (did_init)
        core.deinit();
    if (handle && dlclose(handle) != 0) {
        fprintf(stderr, "error: cannot close core: %s\n", dlerror());
        ok = false;
    }
    free(rom_data);
    free(frame_rgb);
    free(input_events);

    if (ok)
        rc = 0;
    return rc;
}
