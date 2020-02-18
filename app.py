# 3rd party imports
from chalice import Chalice, Response
import numpy as np
import pandas as pd
import arrow

app = Chalice(app_name='simulator')

# helper functions definitions


def timedelta_axis_to_int(df):
    """
    Convert timedelta objects column to int
    """
    return [
        row["days"].days
        for index, row in df.iterrows()
    ]


def calc_interest(rate, current_balance):
    """
    Compute the interest value based on monthly rate
    """
    return current_balance * rate


def calc_balances_and_interest(df, total_amount_released, monthly_release_rate):
    """
    Iterate through df rows in order to compute start balances BOP, 
    interest value and ending balances for each installment plan.
    This computation must be dynamic, beacause each ending balance
    became the start balance for follow month
    """
    next_bop = total_amount_released
    new_df = []
    for index, row in df[1:].iterrows():
        row["begin_balance"] = round(next_bop, 2)
        row["interest"] = round(calc_interest(
            monthly_release_rate, row["begin_balance"]), 2)
        row["ending_balance"] = round(
            row["begin_balance"] + row["interest"] + row["amortization"], 2)
        next_bop = row["ending_balance"]
        new_df.append(row)
    return pd.DataFrame(new_df)


def setup_df(number_of_installments, start_date):
    """
    Return the inicial setup of Data Frame that will be used
    on next computations, basicaly creates the sequence payment plan
    and his payment dates
    """
    month_since_cred_release = pd.Series(np.arange(number_of_installments + 1))
    payment_date = pd.date_range(
        start=start_date, periods=number_of_installments + 1, freq=pd.DateOffset(months=1))
    df = pd.DataFrame(
        {"installment_number": month_since_cred_release, "payment_date": payment_date})
    df["days"] = (df["payment_date"] - df["payment_date"]
                  [0]).fillna(pd.Timedelta(seconds=0))
    df.loc[:, "days"] = timedelta_axis_to_int(df)
    return df


def calc_tax_rate(number_of_days):
    if number_of_days <= 180:
        return 0.2250
    elif number_of_days >= 181 and number_of_days <= 360:
        return 0.2000
    elif number_of_days >= 361 and number_of_days <= 720:
        return 0.1750
    elif number_of_days >= 720:
        return 0.1500


def create_payment_plan(total_amount_released, number_of_installments, monthly_interest_rate, final_iof_payment, monthly_installment, tac, start_date):
    # COMPUTE MONTHLY INSTALLMENT WITH IOF
    total_amount_released += final_iof_payment
    total_amount_released += tac

    # CREATE INITIAL DATAFRAME
    df = setup_df(number_of_installments, start_date)
    # ADD AMORTIZATION AXIS TO DATAFRAME
    df.loc[:, ("amortization")] = monthly_installment * -1
    df.loc[0, ("amortization")] = total_amount_released
    # ADD BALANCES AND INTEREST AXIS STARTING EMPTY
    df.loc[:, "begin_balance"] = ""
    df.loc[1, "begin_balance"] = total_amount_released
    df.loc[:, "ending_balance"] = ""
    df.loc[0, "ending_balance"] = total_amount_released
    df.loc[:, "interest"] = ""
    # COMPUTE INTEREST VALUES AND BALANCES
    df = calc_balances_and_interest(
        df, total_amount_released, monthly_interest_rate)
    # ADD PRINCIPAL AMORTIZATION AXIS
    df.loc[:,
           "principal_amortization"] = (-df["interest"] - df["amortization"])

    # ADJUST THE LASTE INSTALLMENT TO HAVE ENDING BALANCE ZERO
    adjust = df.iloc[-1, 5]
    df.iloc[-1, 6] = df.iloc[-1, 6] - adjust
    df.iloc[-1, 7] = df.iloc[-1, 7] + adjust
    df.iloc[-1, 5] = df.iloc[-1, 5] - adjust
    # CALC RENTAL TAX
    df.loc[:, "tax"] = df.apply(lambda row: round(
        row["interest"] * calc_tax_rate(row["days"]), 2), axis=1)
    return df


@app.route('/hello/{name}')
def hello_name(name):
    # '/hello/james' -> {"hello": "james"}
    return {'hello': name}


@app.route('/simulations', methods=['POST'])
def simulate_loan():
    request_body = app.current_request.json_body
    total_amount_released = request_body['total_amount_released']
    number_of_installments = request_body['number_of_installments']
    monthly_interest_rate = request_body['monthly_interest_rate']
    final_iof_payment = request_body['final_iof_payment']
    monthly_installment = request_body['monthly_installment']
    tac = request_body['tac']
    start_date = request_body['start_date']

    df = create_payment_plan(total_amount_released, number_of_installments,
                             monthly_interest_rate, final_iof_payment, monthly_installment, tac, start_date)

    return Response(status_code=400, headers={'Content-Type': 'application/json'}, body=df.to_json(orient='records', date_format='iso'))


# The view function above will return {"hello": "world"}
# whenever you make an HTTP GET request to '/'.
#
# Here are a few more examples:
#
# @app.route('/hello/{name}')
# def hello_name(name):
#    # '/hello/james' -> {"hello": "james"}
#    return {'hello': name}
#
#
# See the README documentation for more examples.
#
