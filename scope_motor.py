import itertools
import serial
import sys
import time

import numpy


# Minimum number of items to have requested before requesting more items.
# It should take more time for the AVR's ADC to send this number of values
# than it does for the request for more to get through.
REQUEST_LEAD = 500

# Number of items that the AVR will send for a single ADC read invocation.
CHUNK_SIZE = 100

# Hack to support archaic versions of numpy that don't have numpy.percentile.
if hasattr(numpy, "percentile"):
    percentile = lambda a, x: numpy.percentile(a, x)
else:
    import scipy.stats

    percentile = lambda a, x: scipy.stats.scoreatpercentile(a, x)

TTY_DEV = "/dev/ttyUSB0"
TTY_BAUD = 38400

ser = serial.Serial(TTY_DEV, TTY_BAUD)

cmd = sys.argv[1]

def cmd_set_speed():
    while True:
       print "Enter a number between 0 and 255"
       i = int(raw_input())
       if i < 0 or i >= 256:
           raise ValueError
       ser.write(chr(i))

def sample_generator(limit=None):
    requested_remaining = 0
    total_yielded = 0
    def done():
        assert limit is None or total_yielded <= limit
        return limit is not None and total_yielded == limit
    try:
        while not done():
            while not done() and requested_remaining > REQUEST_LEAD:
                c = ser.read()
                yield 1.1 * ord(c) / 256.
                requested_remaining -= 1
                total_yielded += 1

            if not done():
                ser.write(chr(1))
                requested_remaining += CHUNK_SIZE
    finally:
        try:
            while requested_remaining > 0:
                total_yielded += 1
                ser.read()
                requested_remaining -= 1
        except Exception:
            print "Warning: %d items still to be received" % requested_remaining
            raise


def cmd_monitor_adc():
    for val in sample_generator(): 
        print "%f V" % val

def moving_average(a, n=3) :
    ret = numpy.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n

def band_pass(g, short_window_size, long_window_size):
    assert short_window_size < long_window_size
    it = iter(g)

    long_hamming = numpy.hamming(long_window_size)
    long_hamming = long_hamming / numpy.sum(long_hamming)
    short_hamming = numpy.hamming(short_window_size)
    short_hamming = short_hamming / numpy.sum(short_hamming)

    long_window = numpy.zeros((long_window_size,))

    for i in xrange(long_window_size):
        v = next(it)
        long_window[i] = v

    v = next(it)
    while True:
        short_start_idx = (long_window_size / 2) - (short_window_size / 2)
        short_window = long_window[short_start_idx:short_start_idx + short_window_size]
                
        yield (numpy.sum(short_window * short_hamming) -
                numpy.sum(long_window * long_hamming))

        long_window = numpy.roll(long_window, -1)
        long_window[-1] = v

        v = next(it)

def schmitt_trigger(g, buffer_size, lower_percentile=30., upper_percentile=70.):
    it = iter(g)

    buf = numpy.zeros((buffer_size,))

    low = True

    last_low_high_transition = None
    count = 0
    while True:
        for i, v in enumerate(itertools.islice(it, buffer_size)):
            buf[i] = v

        for v in buf:
            if low and v >= percentile(buf, upper_percentile):
                low = False
                if last_low_high_transition is not None:
                    yield count - last_low_high_transition
                last_low_high_transition = count
                
            if not low and v < percentile(buf, lower_percentile):
                low = True

            count += 1

LONG_WINDOW = 500
SHORT_WINDOW = 200
NUM_SAMPLES = 8000
def cmd_plot_adc():
    from matplotlib import pyplot as plt
    
    print "Gathering data" 
    vals = numpy.zeros((NUM_SAMPLES,))
    before = time.time()
    for i, val in enumerate(sample_generator(NUM_SAMPLES)):
        vals[i] = val
    secs = time.time() - before
    print "Seconds per 1000 samples: %f" % (1000. * secs / NUM_SAMPLES)

    plt.plot(list(range(len(vals))), vals)
    
    plt.show()

def cmd_count_cycles():
    print "Flushing buffer"

    g = band_pass(sample_generator(), SHORT_WINDOW, LONG_WINDOW)
    g = schmitt_trigger(g, 1000)
    for num_samples in g:
        # @@@ Time base is no longer accurate
        # One sample = 1.14 ms
        freq = 1000. / num_samples * 1.14
        print "%f samples -> %f Hz" % (num_samples, freq)

# Useful for checking the input buffer has flushed.
def cmd_hello():
    ser.write(chr(2))
    while True:
        print "Got %s:" % repr(ser.read())

cmd_funcs = {
    'set_speed': cmd_set_speed,
    'monitor_adc': cmd_monitor_adc,
    'plot_adc': cmd_plot_adc,
    'count_cycles': cmd_count_cycles,
    'hello': cmd_hello,
    'test_adc': cmd_test_adc,
}

cmd_funcs[cmd]()

