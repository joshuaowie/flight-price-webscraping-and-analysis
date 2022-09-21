import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import Dict
import json
from datetime import datetime
import numpy as np
import streamlit as st
import chart_studio.plotly as py
import plotly.express as px
import cufflinks as cf
import matplotlib
# %matplotlib inline

init_notebook_mode(connected=True)
cf.go_offline()
pd.options.display.float_format = '{:20,.2f}'.format


st.write("""
# Flight Price Comparison between Wakanow Flights and other sites

This app scrapes flight prices of specified routes from various sites and compares to each other
""")

st.write(" ## Please make sure to input approriate parametes at the side bar before continuing below ")
# def concat_flights():
#     all_flights = pd.concat([tiqwa_flights, wakanow_flights, travelstart_flights, travelbeta_flights], axis=1)
#     all_flights.head()
#     return all_flights
# all_flights = concat_flights()


st.sidebar.header("Enter flight details")

departure_date = st.sidebar.date_input("Enter departure date")
st.sidebar.write('Your departure date is:', departure_date)

string_date = str(departure_date)
date_text = str(departure_date) + " 00:00:00.0"

origin = st.sidebar.text_input('Enter origin code', 'LOS')
st.sidebar.write('The current origin code is ', origin)

destination = st.sidebar.text_input('Enter destination code', 'LHR')
st.sidebar.write('The current destination is ', destination)

cabin_class = st.sidebar.selectbox(
    'Enter cabin class', ('economy', 'business', 'first'))
st.sidebar.write('You selected: ', cabin_class)

cabin_class_b = st.sidebar.selectbox(
    'Enter travelbeta cabin class in capital letters', ('ECONOMY', 'BUSINESS', 'FIRST'))
st.sidebar.write('You selected:  ', cabin_class_b)

wakanow_ticket_class = st.sidebar.selectbox(
    'Select Ticket class where Y(Economy), C(Business), "W"(Premium Economy), "F"(First Class)',
    ('Y', 'W', 'C', 'F'))
st.sidebar.write('You selected:', wakanow_ticket_class)

adults = st.sidebar.number_input('Insert a number', 1, 100, 1)
st.sidebar.write('The current number is ', adults)


if 'button_clicked' not in st.session_state:
    st.session_state.button_clicked = False


def callback():
    st.session_state.button_clicked = True


if (st.sidebar.button('Scrape Wakanow Flight', key=4, on_click=callback) or st.session_state.button_clicked):
    @st.cache(allow_output_mutation=True)
    def wakanow():
        wakanow_url: str = "https://flights.wakanow.com/api/flights/Search"

        wakanow_data: Dict = {"FlightSearchType": "Oneway", "Adults": adults, "Children": 0, "Infants": 0, "GeographyId": "NG", "Ticketclass": wakanow_ticket_class, "TargetCurrency": "NGN", "Itineraries": [
            {"Destination": destination, "Departure": origin, "DepartureDate": string_date, "Ticketclass": wakanow_ticket_class}], "FlightRequestView": "{\"FlightSearchType\":\"Oneway\",\"Adults\":1,\"Children\":0,\"Infants\":0,\"GeographyId\":\"NG\",\"Ticketclass\":\"Y\",\"TargetCurrency\":\"NGN\",\"Itineraries\":[{\"Destination\":\"LON\",\"Departure\":\"LOS\",\"DepartureDate\":\"8/26/2022\",\"Ticketclass\":\"Y\",\"DepartureLocationMetaData\":{\"AirportCode\":\"LOS\",\"Description\":\"Murtala Muhammed International Airport (LOS)\",\"CityCountry\":\"Lagos, Nigeria\",\"City\":\"Lagos\",\"Country\":\"Nigeria\",\"Prority\":9},\"DestinationLocationMetaData\":{\"AirportCode\":\"LON\",\"Description\":\"Heathrow (LHR)\",\"CityCountry\":\"London, United Kingdom\",\"City\":\"London\",\"Country\":\"United Kingdom\",\"Prority\":10},\"ReturnDate\":null}]}"}

        wakanow_headers: Dict = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
        }

        # use POST request to collect the flight code for wakanow flight content
        first_request = requests.post(wakanow_url, data=json.dumps(
            wakanow_data), headers=wakanow_headers)

        result_code: str = first_request.json()

        # use get request to collect the flight contents of wakanow website
        result_request = requests.get(
            f"https://flights.wakanow.com/api/flights/SearchV2/{result_code}/NGN", headers=wakanow_headers)

        # Make sure that the request as successul

        # wakanow search data
        flight_result = result_request.json()['SearchFlightResults']

        # search results data as a dataframe
        wakanow_data = pd.json_normalize(flight_result, max_level=1)

        # select required columns from the dataframe
        flight_combination = wakanow_data[[
            'FlightId', 'FlightCombination.Flights', 'FlightCombination.Price']]

        # flatten out the flightcombinations nested json table
        hi = pd.json_normalize(json.loads(
            flight_combination.to_json(orient='records')), max_level=1)

        # rename columns to appropriate properties to avoid nameclashes during merge
        hi.rename({'FlightId': 'SearchId', 'FlightCombination.Price.Amount': 'amount',
                   'FlightCombination.Price.CurrencyCode': 'currency'}, axis=1, inplace=True)

        # flatten out the flights column to retrieve flight details
        flights = pd.json_normalize(json.loads(hi.to_json(
            orient='records')), record_path='FlightCombination.Flights', meta=['SearchId'])
        # drop missing values if any on FlightId column
        flights.dropna(subset=['FlightId'], how='any', inplace=True)
        # reset index
        flights.reset_index(drop=True, inplace=True)

        # flightlegs dataframe i.e the inbetween flight routes
        flightlegs = pd.json_normalize(json.loads(flights.to_json(
            orient='records')), record_path='FlightLegs', meta=['SearchId'])

        # merge hi and flights tables
        wakanow_merge = pd.merge(hi, flights, on='SearchId')
        wakanow_merge.drop('FlightCombination.Flights',
                           axis=1, inplace=True)
        wakanow_merge = pd.merge(
            wakanow_merge, flightlegs[['SearchId', 'CabinClassName']], on='SearchId')

        # select required flight features in a table
        wakanow_flights = wakanow_merge[['SearchId', 'amount', 'currency', 'CabinClassName', 'DepartureTime', 'ArrivalTime', 'TripDuration',
                                        'Airline', 'AirlineName', 'Name', 'DepartureCode', 'ArrivalCode', 'Stops']]

        wakanow_flights = wakanow_flights.add_prefix('wakanow_')
        return wakanow_flights

else:
    st.sidebar.write('No Wakanow Data scraped please scrape data')

wakanow_data = wakanow()


if (st.sidebar.button('Scrape Travelbeta Flight', key=2, on_click=callback) or st.session_state.button_clicked):
    @st.cache(allow_output_mutation=True)
    def travelbeta():
        travelbeta_url: str = "https://api.travelbeta.com/v1/api/flight"

        travelbeta_data: Dict = {"tripDetails": [{"originAirportCode": origin, "destinationAirportCode": destination, "departureDate": date_text, "cabinType": cabin_class_b}], "flightType": "ONE_WAY",
                                 "numberOfAdult": adults, "numberOfChildren": 0, "numberOfInfant": 0, "uniqueSession": "1LcgSi4QOi7yGZ4", "directFlight": True, "refundable": False, "isDayFlight": True, "prefferedAirlineCodes": []}

        travelbeta_headers: Dict = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "x-api-key": "24c9mti53ykc31z1t5u5",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        }

        # use get request to collect the flight contents of travelbeta
        first_request = requests.post(travelbeta_url, data=json.dumps(
            travelbeta_data), headers=travelbeta_headers)

        result: str = json.loads(first_request.text)

        # take note to assign cabin type to final dataframe
        # dataframe of travelstart flight data
        flights_df = pd.json_normalize(result, max_level=1)

        # flatten out nested jsons in dataframe
        travelbeta = pd.json_normalize(json.loads(flights_df.to_json(
            orient='records')), record_path='data.airPricedIternaryList')

        # convert amount in kobo to naira
        travelbeta['amountInNaira'] = travelbeta['amountInKobo'] / 100

        # origin to destination data and drop airline name to avoid name clashes during merge
        lists = pd.json_normalize(json.loads(travelbeta.to_json(
            orient='records')), record_path='airOriginDestinationList', meta=['id'])
        lists.drop('airlineName', axis=1, inplace=True)

        # merge both dataframes into a single dataframe
        travelbeta_merge = pd.merge(travelbeta, lists, on='id')

        # select required information from the dataframe
        travelbeta_flights = travelbeta_merge[['id', 'amountInNaira', 'firstDepartureTime', 'lastArrivalTime', 'totalFlightTimeInMs',
                                               'airlineCode', 'airlineName', 'originCityCode', 'destinationCityCode', 'totalStop']]

        travelbeta_flights = travelbeta_flights.add_prefix('travelbeta_')

        return travelbeta_flights

else:
    st.sidebar.write('No Travelbeta Data scraped please scrape data')

travelbeta_data = travelbeta()


if (st.sidebar.button('Scrape Travelstart Flight', key=3, on_click=callback) or st.session_state.button_clicked):
    @st.cache(allow_output_mutation=True)
    def travelstart():
        travelstart_url: str = "https://wapi.travelstart.com/website-services/api/search/?affid=ng-adwords-brand&gclid=CjwKCAjwrZOXBhACEiwA0EoRD2l3p-TJt9jX6NQq7_17MPfPiIJ6cMWbDi1-5-XQZrv-EoVIl9RC0hoCrA8QAvD_BwE&gclsrc=aw.ds&language=en&correlation_id=ae2a22e4-0c64-4a28-81c3-01fd9a2d1690"

        travelstart_data: Dict = {"tripType": "oneway", "isNewSession": True, "travellers": {"adults": adults, "children": 0, "infants": 0}, "moreOptions": {"preferredCabins": {"display": "Economy", "value": cabin_class}, "isCalendarSearch": False}, "outboundFlightNumber": "", "inboundFlightNumber": "", "itineraries": [{"id": "979eed77-cb21-48df-9e7f-00644fb1ce4a", "origin": {"value": {"type": "airport", "city": "Lagos", "airport": "Murtala Muhammed International Airport", "iata": origin, "code": origin, "country": "Nigeria", "countryIata": "NG", "locationId": "airport_LOS"}, "display": "Lagos Murtala Muhammed International Airport"}, "destination": {
            "value": {"type": "city", "city": "London", "airport": "All Airports", "iata": destination, "code": destination, "country": "United Kingdom", "countryIata": "GB", "locationId": "GB_city_LON"}, "display": "London All Airports"}, "departDate": string_date, "returnDate": "null"}], "searchIdentifier": "", "locale": {"country": "NG", "currentLocale": "en", "locales": []}, "userProfileUsername": "", "businessLoggedOnToken": "", "isDeepLink": False}

        travelstart_headers: Dict = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "ts-country": "NG",
            "ts-language": "en",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        }

        # use get request to collect the flight contents of travelstart
        first_request = requests.post(travelstart_url, data=json.dumps(
            travelstart_data), headers=travelstart_headers)

        result: str = json.loads(first_request.text)

        # dataframe from json flight data
        travelstart_data = pd.DataFrame(result)

        # itineraries table
        itineraries_index = travelstart_data.loc['itineraries']['response']
        itineraries = pd.json_normalize(itineraries_index, max_level=0)

        # price table
        price = itineraries[['id', 'amount', 'currencyCode']]
        price['amount'] = price['amount'].astype(float)

        # flatte out the list of nested json table to get flight details
        odolist = pd.json_normalize(json.loads(itineraries.to_json(
            orient='records')), record_path='odoList', meta=['id'])

        # flatten out list of nested json to get flight segments
        travelstart = pd.json_normalize(json.loads(odolist.to_json(
            orient='records')), record_path='segments', meta=['id'])

        # merge price and flight details(travelstart) table
        travelstart_merge = pd.merge(price, travelstart, on='id')

        # select required flight details and price
        travelstart_flights = travelstart_merge[['id', 'amount', 'currencyCode', 'cabinClass', 'departureDateTime', 'arrivalDateTime',
                                                'duration', 'airlineCode', 'flightNumber', 'origCode', 'destCode', 'technicalStops']]

        travelstart_flights = travelstart_flights.add_prefix(
            'travelstart_')
        return travelstart_flights

else:
    st.sidebar.write('No Travelstart Data scraped please scrape data')

travelstart_data = travelstart()
# except:
#     st.warning("Travelstart Flight not scraped!")
#     st.stop


# try:
if st.button('Combine all Flight data', key=5):
    all_flights = pd.concat(
        [wakanow_data, travelstart_data, travelbeta_data], axis=1)

    st.write(all_flights)
    st.write('------')

    all_flights[['wakanow_amount', 'travelstart_amount', 'travelbeta_amountInNaira']] = all_flights[[
        'wakanow_amount', 'travelstart_amount', 'travelbeta_amountInNaira']].fillna(0)

else:
    st.write("No Combined data! Press to combine scraped data")


fig = px.bar(all_flights, y=['wakanow_amount', 'travelstart_amount', 'travelbeta_amountInNaira'], labels={'value': 'company flight amount'},
             hover_data=['wakanow_DepartureCode', 'wakanow_ArrivalCode', 'wakanow_DepartureTime', 'wakanow_ArrivalTime'])

fig.update_layout(bargap=0.2)


# create wakanow subplots layout
fig_wakanow = make_subplots(rows=1, cols=2, shared_yaxes=False, subplot_titles=(
    "Wakanow Airline by Amounts", "Wakanow Arrival and Departure Time by Amount Distribution"))

# add subplots to the layout
fig_wakanow.add_trace(go.Histogram(
    x=wakanow_data['wakanow_AirlineName'], y=wakanow_data['wakanow_amount'], name="airline flights amounts", histfunc="sum"), 1, 1)

fig_wakanow.add_trace(go.Histogram(
    x=wakanow_data['wakanow_ArrivalTime'], y=wakanow_data['wakanow_amount'], name="arrival time", histfunc="sum"), 1, 2)

fig_wakanow.add_trace(go.Histogram(x=wakanow_data['wakanow_DepartureTime'],
                      y=wakanow_data['wakanow_amount'], name="departure time", histfunc="sum"), 1, 2)


# Update xaxis properties
fig_wakanow.update_xaxes(title_text="airlines", row=1, col=1)
fig_wakanow.update_xaxes(title_text="arrival and departure time", row=1, col=2)


# Update yaxis properties
fig_wakanow.update_yaxes(title_text="price amount ", row=1, col=1)
fig_wakanow.update_yaxes(title_text="price amount",  row=1, col=2)


# update layout
fig_wakanow.update_layout(showlegend=True, bargap=0.2,
                          title_text="Wakanow plots")


# create travelstart subplots layout
fig_travelstart = make_subplots(rows=1, cols=2, shared_yaxes=False, subplot_titles=(
    "Travelstart Airline by Amounts", "Travelstart Arrival and Departure Time by Amount Distribution"))

# add subplots to the layout
fig_travelstart.add_trace(go.Histogram(x=travelstart_data['travelstart_airlineCode'],
                          y=travelstart_data['travelstart_amount'], name="airline flights amounts", histfunc="sum"), 1, 1)

fig_travelstart.add_trace(go.Histogram(x=travelstart_data['travelstart_arrivalDateTime'],
                          y=travelstart_data['travelstart_amount'], name="arrival time", histfunc="sum"), 1, 2)

fig_travelstart.add_trace(go.Histogram(x=travelstart_data['travelstart_departureDateTime'],
                          y=travelstart_data['travelstart_amount'], name="departure time", histfunc="sum"), 1, 2)


# Update xaxis properties
fig_travelstart.update_xaxes(title_text="airlines", row=1, col=1)
fig_travelstart.update_xaxes(
    title_text="arrival and departure time", row=1, col=2)


# Update yaxis properties
fig_travelstart.update_yaxes(title_text="price amount ", row=1, col=1)
fig_travelstart.update_yaxes(title_text="price amount", row=1, col=2)


# update layout
fig_travelstart.update_layout(
    showlegend=True, bargap=0.2, title_text="Travelstart plots")


# create travelbeta subplot layout
fig_travelbeta = make_subplots(rows=1, cols=2, shared_yaxes=False, subplot_titles=(
    "Travelbeta Airline by Amounts", "Travelbeta Arrival and Departure Time by Amount Distribution"), )
#                     specs=[[{"colspan": 2}, None]
#                            [{"colspan": 2}, None]])

# add subplots to the layout
fig_travelbeta.add_trace(go.Histogram(x=travelbeta_data['travelbeta_airlineName'],
                         y=travelbeta_data['travelbeta_amountInNaira'], name="airline flights amounts", histfunc="sum"), 1, 1)

fig_travelbeta.add_trace(go.Histogram(x=travelbeta_data['travelbeta_lastArrivalTime'],
                         y=travelbeta_data['travelbeta_amountInNaira'], name="arrival time", histfunc="sum"), 1, 2)

fig_travelbeta.add_trace(go.Histogram(x=travelbeta_data['travelbeta_firstDepartureTime'],
                         y=travelbeta_data['travelbeta_amountInNaira'], name="departure time", histfunc="sum"), 1, 2)


# Update xaxis properties
fig_travelbeta.update_xaxes(title_text="airlines", row=1, col=1)
fig_travelbeta.update_xaxes(
    title_text="arrival and departure time", row=1, col=1)


# Update yaxis properties
fig_travelbeta.update_yaxes(title_text="price amount ", row=1, col=1)
fig_travelbeta.update_yaxes(title_text="price amount", row=1, col=2)


# update layout
fig_travelbeta.update_layout(
    showlegend=True, bargap=0.2, title_text="Travelbeta plots")


st.write(fig)
st.write(fig_wakanow)
st.write(fig_travelstart)
st.write(fig_travelbeta)
