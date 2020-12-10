"""Script for getting information about fligths from www.airblue.com.

Functions:
    get_times: get all time information for flight.
    get_prices: get information about cost and currency.
    get_page: get primary object for parsing.
    get_travel_data: get main travel data.
    get_iata_list: get IATA-codes from site.
    check_iata: checking IATA-codes.
    format_date: check each date.
    check_date: final checking for date arguments.
    validate_args_quantity: checking arguments quantity.
    validate_args: main function for checking arguments.
    convert_data: convertation data to user-friendly form.
    total_cost: key function, also calculete total cost.
    print_travel_options: controls the printing of results.
    search_flights: main function.
    main: function for starting.

Note about .fromisoformat() convertation. I deside to  return date in str form
in format_date() function, because it's more convinient way to work with it in
future. Of cousre, year, month and day could be parsed from datetime object in
other functions, but it will be more difficult to format messeges to user in
print_travel_options(), for example.
Note about regular expressions. For using re module in get_prices, I found two
reasons. First, it impose severe restrictions on what we are looking for.
Second, reg-ex finds price and currency separately and we can to convert price
to float format without any additional movements.

"""

import sys
import re
import datetime
from itertools import product
from collections import namedtuple
import requests
from lxml.html import fromstring, tostring
from prettytable import PrettyTable


Journey = namedtuple('Travel', ['From', 'To', 'Departure', 'Arrival',
                                'Flight_time', 'Class', 'Price'])
TABLE_HEAD = ('From', 'To', 'Departure', 'Arrival',
              'Flight time', 'Class', 'Price')


def get_times(travel, date):
    """Get departure time arrival time and flight duration for flight.

    Args:
        travel: lxml.html object.
        date(str): date of flight, like '2020-02-02'.
    Returns:
        tuple: datetime objects for departure time and arrival time,
        string for flight duration.

    First, function gets departure and arrival time for flight. Second, its
    create datetime objects from the obtained values, compares them with
    each other, and, if arrival-time object is lesser, then departure-time
    object, adds 1 day to it.Third, calculete flight duration and form
    string which represents result.

    """

    time_leaving = travel.xpath('./td[@class="time leaving"]').pop().text
    time_landing = travel.xpath('./td[@class="time landing"]').pop().text
    dt_leaving = datetime.datetime.strptime(f'{date}-{time_leaving}',
                                            '%Y-%m-%d-%I:%M %p')
    dt_landing = datetime.datetime.strptime(f'{date}-{time_landing}',
                                            '%Y-%m-%d-%I:%M %p')
    if dt_leaving > dt_landing:
        dt_landing += datetime.timedelta(days=1)
    time_on_air = dt_landing - dt_leaving
    hours = time_on_air.seconds // 3600
    minutes = time_on_air.seconds % 3600 // 60
    flight_time = f'{hours} hour(s) {minutes} minute(s)'
    return dt_leaving, dt_landing, flight_time


def get_prices(travel, rates):
    """ Get information about cost and currency for each  possible class.

    Args:
        travel: lxml.html object.
        rates(list): list of strings with names of classes.
    Returns:
        dictionary: dictionary with classnames as keys and tuple with cost
        (float) and currency (srt) as values.

    I deside to use regular expressions because it impose severe restrictions
    on what we are looking for. Currency ([A-Z]{3}) and cost([0-9,.]+) is all
    I want from this searching. If .text_content() method is used we may get
    'SOLD OUT' or another text message for  some classes. Iteration through
    prices dictionary helps to filter classes without information about cost.

    """

    prices_path = './td[contains(@class, "family family-")]/label'
    prices = dict()
    for rate, price_item in zip(rates, travel.xpath(prices_path)):
        money = re.search(r'([A-Z]{3})\s([0-9,.]+)[\s"]',
                          tostring(price_item).decode())
        if money:
            prices[rate] = (float(money.group(2).replace(',', '')),
                            money.group(1))
    return prices


def get_page(dep_iata, arr_iata, dep_date, arr_date=None):
    """Get primary object for parsing.

    Args:
        dep_iata(str): IATA-code of departure airport.
        arr_iata(str): IATA-code of arrival airport.
        dep_date(str): departure date, like '2020-02-02'.
        arr_date(str): arrival date, like '2020-02-02'. Optional argument.
            Default to None.
    Returns:
        lxml.html object.
    Raises:
        RequestException: for catching any request errors.

    Create a dictionary with parameters for requests.get. Try to send
    a request, catch an exception.

    """

    base_url = 'https://www.airblue.com/bookings/flight_selection.aspx'

    params = {'FL': 'on', 'PA': '1', 'TT': 'OW'}

    params.update(DC=dep_iata, AC=arr_iata, AM=dep_date[:-3], AD=dep_date[-2:])
    if arr_date:
        params.update(TT='RT', RM=arr_date[:-3], RD=arr_date[-2:])
    try:
        response = requests.get(base_url, params=params)
    except requests.exceptions.RequestException:
        print('An unexpected connection error has occurred')
        sys.exit()
    parsed_page = fromstring(response.text)
    return parsed_page


def get_travel_data(parsed_page, date, where_from, where_to, number=1):
    """Get main travel data.

    Args:
        parsed_page: lxml.html object.
        date(str): date of flight, like '2020-02-02'.
        where_from(str): IATA-code of departure point.
        where_to(str): IATA-code of destination.
        number(int): number of flight which is used for creating xpath.
            Default to 1.
    Returns:
        list: list of namedtuples with information about each possible flight
            or empty list if there is no flights for selected date.

    Create argument for xpath expression using unique id with date and number
    of flight. If any elements found, search information about classes and
    create list of classes for get_prices. Call special functions for each
    found object  to get data. Make namedtuples with results of its work.

    """

    basic_path = f'.//table[@id="trip_{number}_date_{date.replace("-", "_")}"]'
    travel_list = parsed_page.xpath(basic_path +
                                    '/tbody/tr[@class="flight-status-ontime"]')

    if travel_list:
        rates = [rate_item.text_content().split()[0] for rate_item
                 in parsed_page.xpath(basic_path + '/thead/tr/th/span')]

        travel_details = []
        for travel in travel_list:
            times = get_times(travel, date)
            prices = get_prices(travel, rates)
            for flight_class, price in prices.items():
                journey = Journey(where_from, where_to, *times,
                                  flight_class, price)
                travel_details.append(journey)
    else:
        travel_details = []
    return travel_details


def get_iata_list():
    """Get IATA-codes from site.

    Returns:
        list: list of IATA-codes(str)
    Raises:
        RequestException: for catching any request errors.

    Try to get IATAs from site. If this is not possible, interrupt the program.

    """

    try:
        response = requests.get('https://www.airblue.com/')
    except requests.exceptions.RequestException:
        print('An unexpected connection error has occurred')
        sys.exit()
    parsed_page = fromstring(response.text)
    if parsed_page.xpath('.//title').pop().text == 'Too Many Requests':
        print('Sorry, the server is overloaded. Try again later.')
        sys.exit()
    path = './/select[@name="AC"]/option[position()>1]/@value'
    iata_list = parsed_page.xpath(path)
    return iata_list


def check_iata(dep_iata, arr_iata):
    """Checking IATA-codes.

    Args:
        dep_iata(str): IATA-code of departure airport.
        arr_iata(str): IATA-code of arrival airport.
    Returns:
        tuple: tuple of  uppercase strings.

    If IATA is incorrect or the company doesn't fly from/to this city or
    departure-IATA coincides with arrival-IATA, script asks user to re-enter
    inappropriate IATA(s).

    """

    iata_list = get_iata_list()
    while True:
        dep_iata = dep_iata.upper()
        arr_iata = arr_iata.upper()
        if dep_iata not in iata_list:
            print('Departure-IATA is incorrect')
            dep_iata = input('Please, enter departune airport IATA(ABC): ')
        elif arr_iata not in iata_list:
            print('Arrival-IATA is incorrect')
            arr_iata = input('Please, enter arrival airport IATA(ABC): ')
        elif dep_iata == arr_iata:
            print('Departure-IATA coincides with arrival-IATA')
            dep_iata = input('Please, enter departune airport IATA(ABC): ')
            arr_iata = input('Please, enter arrival airport IATA(ABC): ')
        else:
            break
    return dep_iata, arr_iata


def format_date(date, date_type):
    """Check each date.

    Args:
        date(str): date of flight, like '2020-02-02'.
        date_type(str): flight type(departure, arrival)
    Returns:
        srt: date in str format, because it’s more convenient to work with
            it in the future.

    Check date arguments for correct format. Also check  date for not being
    eirlier than current  date or not not being too much in future(1 year).

    """

    today = datetime.date.today()
    while True:
        try:
            dt_date = datetime.date.fromisoformat(date)
            assert today <= dt_date <= today + datetime.timedelta(days=365)
            return date
        except (ValueError, AssertionError):
            print(f'Incorrect {date_type} date')
            date = input(f'Please, enter {date_type} date(YYYY-MM-DD): ')


def check_date(dep_date, arr_date=None):
    """Final checking for date arguments.

    Args:
        dep_date(str): departure date, like '2020-02-02'.
        arr_date(str): arrival date, like '2020-02-02'. Optional argument.
            Default to None.
    Returns:
        tuple: tuple of strings with dates(arrival date may be None).

    The arrival date must  be later than the departure date.

    """

    dep_date = format_date(dep_date, 'departure')
    if arr_date:
        while True:
            arr_date = format_date(arr_date, 'arrival')
            if (datetime.date.fromisoformat(arr_date) <
                    datetime.date.fromisoformat(dep_date)):
                print('Departure date is later than arrival date')
                arr_date = input('Please, enter arrival date(YYYY-MM-DD): ')
            else:
                break
    return dep_date, arr_date


def validate_args_quantity(func):
    """Decorator function for checking arguments quantity."""

    def wrapper(*args):
        while len(args) < 3 or len(args) > 4:
            print('Wrong number of search parametrs')
            print('Please enter correct parametrs for searching')
            print('Example: KHI ISB 2020-01-31 2020-01-31')
            params = input()
            args = params.split()
        func(*args)
    return wrapper


def validate_args(func):
    """Decorator function for checking arguments."""

    def wrapper(dep_iata, arr_iata, dep_date, arr_date=None):
        dep_iata, arr_iata = check_iata(dep_iata, arr_iata)
        dep_date, arr_date = check_date(dep_date, arr_date)
        func(dep_iata, arr_iata, dep_date, arr_date)
    return wrapper


def convert_data(travel):
    """Convertation data to user-friendly form."""

    converted_data = list(travel[:-1])
    pretty_price = str(travel.Price[0]) + ' ' + travel.Price[1]
    converted_data.append(pretty_price)
    return converted_data


def total_cost(travel_combination):
    """Key function for sorting. Also calculetes total cost."""

    return travel_combination[0].Price[0] + travel_combination[1].Price[0]


def print_travel_options(first_travel, dep_date,
                         arr_date=None, second_travel=None):
    """Function for controlling the printing of results.

    Args:
        first_travel: namedtuple with travel information.
        dep_date(str): departure date, like '2020-02-02'.
        arr_date(str): arrival date, like '2020-02-02'. Default to None.
        second_travel: namedtuple with travel information. Default to None.

    Print table(s) with information about travels. Tables is sorted by total
    cost for return flight and by simple cost for oneway trip. If fligths are
    not availble for some reason, function prints message about it.

    """

    if arr_date:
        if not first_travel or not second_travel:
            print(f'Flights are not available on {dep_date} and {arr_date}')
        else:
            flights_comb_list = []
            for outbound, inbound in product(first_travel, second_travel):
                if (dep_date == arr_date and
                        outbound.Arrival > inbound.Departure):
                    continue
                flights_comb_list.append((outbound, inbound))
            if not flights_comb_list:
                print(f'Flights  are not available on {dep_date}')
            for outbound, inbound in sorted(flights_comb_list,
                                            key=total_cost):
                print('*' * 50)
                table = PrettyTable(TABLE_HEAD)
                table.add_row(convert_data(outbound))
                table.add_row(convert_data(inbound))
                print(table)
                print('Total cost: ', total_cost((outbound, inbound)),
                      outbound.Price[1])
    else:
        if not first_travel:
            print(f'Flights  are not available on {dep_date}')
        else:
            for travel in sorted(first_travel,
                                 key=lambda travel: travel.Price[0]):
                print('*' * 50)
                table = PrettyTable(TABLE_HEAD)
                table.add_row(convert_data(travel))
                print(table)


@validate_args_quantity
@validate_args
def search_flights(dep_iata, arr_iata, dep_date, arr_date=None):
    """Main function, which calls  child functions."""

    parsed_page = get_page(dep_iata, arr_iata, dep_date, arr_date)
    if parsed_page.xpath('.//title').pop().text == 'Too Many Requests':
        print('Sorry, the server is overloaded. Try again later.')
        sys.exit()

    first_travel = get_travel_data(parsed_page, dep_date,
                                   dep_iata, arr_iata)
    if arr_date:
        second_travel = get_travel_data(parsed_page, arr_date,
                                        arr_iata, dep_iata, number=2)
        print_travel_options(first_travel, dep_date,
                             arr_date, second_travel)
    else:
        print_travel_options(first_travel, dep_date)


def main():
    """ Simple starter function."""

    args = sys.argv[1:]
    if args:
        search_flights(*args)
    else:
        print('1', '#'*30)
        search_flights('KHI', 'JED', '2020-02-19')
        print('2', '#'*30)
        search_flights('JED', 'ISB', '2020-02-17')
        print('3', '#'*30)
        search_flights('KHI', 'ISB', '2020-02-19')
        print('4', '#'*30)
        search_flights('ISB', 'AUH', '2020-02-27', '2020-02-27')
        print('5', '#'*30)
        search_flights('AUH', 'ISB', '2020-02-27', '2020-02-27')
        print('6', '#'*30)
        search_flights('KHI', 'ISB', '2020-02-27', '2020-02-29')
        print('7', '#'*30)
        search_flights('DXB', 'MED', '2020-02-25', '2020-02-29')
        print('8', '#'*30)
        search_flights('DXB', 'MUX', '2020-02-27', '2020-02-29')
        print('9', '#'*30)
        search_flights('MUX', 'DXB', '2020-02-27', '2020-02-29')
        print('10', '#'*30)
        search_flights('MUX', 'MUX', '2020-02-27', '2020-02-29')
        print('11', '#'*30)
        search_flights('KHI', 'ISB', '2020-01-27', '2020-02-29')
        print('12', '#'*30)
        search_flights('khi', 'Isb', '2020.02.27', '2020ю02ю29')
        print('13', '#'*30)
        search_flights('KHI', 'ISB', '2020-01-29', '2020-02-27')
        print('14', '#'*30)
        search_flights('KHI', 'ISB')
        print('15', '#'*30)
        search_flights('KHI', 'ISB', '2020-01-27', '2020-02-28', '2020-02-29')


if __name__ == '__main__':
    main()
