"""
Algorithm for computing sunrise and sunset

This file written in a literate style[1] where the design document[2] is
embedded directly in the code as docstrings.

Source: http://williams.best.vwh.net/sunrise_sunset_algorithm.htm
"""
from __future__ import division
from __future__ import print_function

import datetime
from math import floor

from sunset.trig import sin, cos, tan, asin, acos, atan
from sunset.utils import DMS_to_decimal


DEBUG = False


class NoSunrise(Exception):
    pass


class NoSunset(Exception):
    pass


"""
Sunrise/Sunset Algorithm

Source:
    Almanac for Computers, 1990
    published by Nautical Almanac Office
    United States Naval Observatory
    Washington, DC 20392

Inputs:
    day, month, year:      date of sunrise/sunset
    latitude, longitude:   location for sunrise/sunset
    zenith:                Sun's zenith for sunrise/sunset
      offical      = 90 degrees 50'
      civil        = 96 degrees
      nautical     = 102 degrees
      astronomical = 108 degrees
"""

ZENITHS = {
    "official": DMS_to_decimal(90, 50, 0),
    "civil": 96,
    "nautical": 102,
    "astronomical": 108
}

"""
    NOTE: longitude is positive for East and negative for West
        NOTE: the algorithm assumes the use of a calculator with the
        trig functions in "degree" (rather than "radian") mode. Most
        programming languages assume radian arguments, requiring back
        and forth convertions. The factor is 180/pi. So, for instance,
        the equation RA = atan(0.91764 * tan(L)) would be coded as RA
        = (180/pi)*atan(0.91764 * tan((pi/180)*L)) to give a degree
        answer with a degree input for L.
"""
def _get_day_of_year_step_1(day, month, year):
    """
    1. first calculate the day of the year

        N1 = floor(275 * month / 9)
        N2 = floor((month + 9) / 12)
        N3 = (1 + floor((year - 4 * floor(year / 4) + 2) / 3))
        N = N1 - (N2 * N3) + day - 30
    """
    N1 = floor(275 * month / 9)
    N2 = floor((month + 9) / 12)
    N3 = (1 + floor((year - 4 * floor(year / 4) + 2) / 3))
    N = N1 - (N2 * N3) + day - 30
    return N  # days


def _get_rising_or_setting_time_step_2(N, longitude, mode):
    """
    2. convert the longitude to hour value and calculate an approximate time

        lngHour = longitude / 15

        if rising time is desired:
          t = N + ((6 - lngHour) / 24)
        if setting time is desired:
          t = N + ((18 - lngHour) / 24)
    """
    lngHour = longitude / 15

    if mode == 'rising':
        t = N + ((6 - lngHour) / 24)
    elif mode == 'setting':
        t = N + ((18 - lngHour) / 24)
    else:
        raise ValueError("unknown mode, must be 'rising' or 'setting'")

    return t  # days


def _get_suns_mean_anomaly_step_3(t):
    """
    3. calculate the Sun's mean anomaly

        M = (0.9856 * t) - 3.289
    """
    M = (0.9856 * t) - 3.289
    return M  # degrees


def _get_suns_true_longitude_step_4(M):
    """
    4. calculate the Sun's true longitude

        L = M + (1.916 * sin(M)) + (0.020 * sin(2 * M)) + 282.634
        NOTE: L potentially needs to be adjusted into the range [0,360) by adding/subtracting 360
    """
    L = M + (1.916 * sin(M)) + (0.020 * sin(2 * M)) + 282.634
    return L % 360  # degrees


def _get_suns_right_ascension_step_5a(L):
    """
    5a. calculate the Sun's right ascension

        RA = atan(0.91764 * tan(L))
        NOTE: RA potentially needs to be adjusted into the range [0,360) by adding/subtracting 360
    """
    RA = atan(0.91764 * tan(L))
    return RA % 360  # degrees


def _get_suns_right_ascension_step_5b(L, RA):
    """
    5b. right ascension value needs to be in the same quadrant as L

        Lquadrant  = (floor( L/90)) * 90
        RAquadrant = (floor(RA/90)) * 90
        RA = RA + (Lquadrant - RAquadrant)
    """
    Lquadrant  = (floor(L/90)) * 90
    RAquadrant = (floor(RA/90)) * 90
    RA = RA + (Lquadrant - RAquadrant)
    return RA  # degrees


def _get_suns_right_ascension_step_5c(RA):
    """
    5c. right ascension value needs to be converted into hours

        RA = RA / 15
    """
    RA = RA / 15
    return RA  # hours


def _get_suns_declination_sin_and_cos_step_6(L):
    """
    6. calculate the Sun's declination

        sinDec = 0.39782 * sin(L)
        cosDec = cos(asin(sinDec))
    """
    sinDec = 0.39782 * sin(L)
    cosDec = cos(asin(sinDec))
    return sinDec, cosDec  # scalars


def _get_suns_local_hour_angle_step_7a(zenith, latitude, sinDec, cosDec):
    """
    7a. calculate the Sun's local hour angle

        cosH = (cos(zenith) - (sinDec * sin(latitude))) / (cosDec * cos(latitude))

        if (cosH >  1) 
          the sun never rises on this location (on the specified date)
        if (cosH < -1)
          the sun never sets on this location (on the specified date)
    """
    cosH = (cos(zenith) - (sinDec * sin(latitude))) / (cosDec * cos(latitude))

    if cosH > 1:
        raise NoSunrise("cosH={0}".format(cosH))
    elif cosH < -1:
        raise NoSunset("cosH={0}".format(cosH))

    return cosH  # scalar


def _get_suns_local_hour_angle_step_7b(cosH, mode):
    """
    7b. finish calculating H and convert into hours

        if rising time is desired:
          H = 360 - acos(cosH)
        if setting time is desired:
          H = acos(cosH)

        H = H / 15
    """
    if mode == 'rising':
        H = 360 - acos(cosH)
    elif mode == 'setting':
        H = acos(cosH)
    else:
        raise ValueError("unknown mode, must be 'rising' or 'setting'")

    H = H / 15
    return H  # hours


def _get_local_mean_time_rising_or_setting_step_8(H, RA, t):
    """
    8. calculate local mean time of rising/setting

        T = H + RA - (0.06571 * t) - 6.622
    """
    T = H + RA - (0.06571 * t) - 6.622
    return T  # hours


def _get_local_mean_time_rising_or_setting_as_UTC_step_9(T, longitude):
    """
    9. adjust back to UTC

        UT = T - lngHour
        NOTE: UT potentially needs to be adjusted into the range [0,24) by adding/subtracting 24
    """
    lngHour = longitude / 15

    UT = T - lngHour
    return UT % 24  # hours


def _get_local_mean_time_rising_or_setting_as_local_time_step_10(UT, localOffset):
    """
    10. convert UT value to local time zone of latitude/longitude

        localT = UT + localOffset
    """
    localT = UT + localOffset
    return localT % 24  # hours


def log(s):
    if DEBUG:
        print(s)


def log_step(step, description, var, val):
    if DEBUG:
        log('\t'.join(["{0} =".format(var).ljust(10),
                       '{0:.3f}'.format(val).rjust(10),
                       description.ljust(55),
                       '(step {0})'.format(step)]))


def _get_sunset_or_sunrise(mode, day, month, year, latitude, longitude,
                          localOffset, zenith):
    zenith = ZENITHS[zenith]

    N = _get_day_of_year_step_1(day, month, year)
    log_step('1', 'Day of year', 'N', N)

    t = _get_rising_or_setting_time_step_2(N, longitude, mode)
    log_step('2', "Rising or setting time", 't', t)

    M = _get_suns_mean_anomaly_step_3(t)
    log_step('3', "Sun's mean anomaly", 'M', M)

    L = _get_suns_true_longitude_step_4(M)
    log_step('4', "Sun's true longitude", 'L', L)

    RA = _get_suns_right_ascension_step_5a(L)
    log_step('5a', "Sun's right ascension", 'RA', RA)

    RA = _get_suns_right_ascension_step_5b(L, RA)
    log_step('5b', "Sun's right ascension", 'RA', RA)

    RA = _get_suns_right_ascension_step_5c(RA)
    log_step('5c', "Sun's right ascension", 'RA', RA)

    sinDec, cosDec = _get_suns_declination_sin_and_cos_step_6(L)
    log_step('6', "Sin of sun's declination", 'sinDec', sinDec)
    log_step('6', "Cos of sun's declination", 'cosDec', cosDec)

    cosH = _get_suns_local_hour_angle_step_7a(zenith, latitude, sinDec, cosDec)
    log_step('7a', "Sun's local hour angle", 'cosH', cosH)

    H = _get_suns_local_hour_angle_step_7b(cosH, mode)
    log_step('7b', "Sun's local hour angle", 'H', H)

    T = _get_local_mean_time_rising_or_setting_step_8(H, RA, t)
    log_step('8', "Sun's local mean time rising or setting", 'T', T)

    UT = _get_local_mean_time_rising_or_setting_as_UTC_step_9(T, longitude)
    log_step('9', "Sun's local mean time rising or setting in UTC", 'UT', UT)

    localT = _get_local_mean_time_rising_or_setting_as_local_time_step_10(UT, localOffset)
    log_step('10', "Sun's local mean time rising or setting in local time", 'localT', localT)

    return localT


def _get_sunset_or_sunrise_datetime(mode, date, latitude, longitude, utc_offset,
                           zenith):
    day = date.day
    month = date.month
    year = date.year

    try:
        local_time_hours = _get_sunset_or_sunrise(
            mode, day, month, year, latitude, longitude, utc_offset, zenith)
    except (NoSunrise, NoSunset):
        return None

    return (datetime.datetime(year, month, day) +
            datetime.timedelta(hours=local_time_hours))


# Public functions

def get_sunrise(date, latitude, longitude, utc_offset, zenith='official',
                **kwargs):
    """Returns sunrise as a `datetime` or `None` if there is no sunrise for
    this location on the given date.

    date: `datetime.date` object representing the desired date
    latitude: latitude in decimal degrees
    longitude: longitude in decimal degrees
    utc_offset: offset from UTC in hours (e.g. -5 is CDT)
    zenith: standard definition of sunrise ('official, 'civil', 'nautical',
            'astronomical')
    """
    return _get_sunset_or_sunrise_datetime(
            'rising', date, latitude, longitude, utc_offset, zenith)


def get_sunset(date, latitude, longitude, utc_offset, zenith='official',
               **kwargs):
    """Returns sunset as a `datetime` or `None` if there is no sunset for this
    location on the given date.

    date: `datetime.date` object representing the desired date
    latitude: latitidue in decimal degrees
    longitude: longitude in decimal degrees
    utc_offset: offset from UTC in hours (e.g. -5 is CDT)
    zenith: standard definition of sunset ('official, 'civil', 'nautical',
            'astronomical')
    """
    return _get_sunset_or_sunrise_datetime(
            'setting', date, latitude, longitude, utc_offset, zenith)



if __name__ == "__main__":
    today = datetime.date.today()

    # Position (Austin, TX)
    latitude = DMS_to_decimal(30, 16, 59)
    longitude = DMS_to_decimal(-97, -43, -59)

    # UTC offset (CDT)
    utc_offset = -5

    print(' '.join([
        'Zenith Name'.ljust(20),
        'Sunrise'.ljust(20),
        'Sunset'
    ]))

    print("=" * 53)

    for zenith in ('official', 'civil', 'nautical', 'astronomical'):
        sunset = get_sunset(today, latitude, longitude, utc_offset,
                            zenith=zenith)

        sunrise = get_sunrise(today, latitude, longitude, utc_offset,
                              zenith=zenith)

        print(' '.join([
            zenith.ljust(20),
            sunrise.strftime("%I:%M:%S %p").ljust(20),
            sunset.strftime("%I:%M:%S %p")
        ]))
