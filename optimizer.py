# Import dependencies
import pandas as pd
import numpy as np
import pulp as pl
import matplotlib.pyplot as plt
import math
import os
import datetime
from azure.storage.file import FileService



# Define global variables
AzureStorageAccount = 'effiles'    # Specify Azure storage account name
key = 'axLykwdLsUwKTDY5flU6ivGrt9obV38k2UMVDCSpLYE3K6jAkwsjWOThQydhuMSWHfx6lTq102gdkas/GyKhEA=='    # 

file_service = FileService(account_name = AzureStorageAccount, account_key = key) 
path1 = 'efficientfrontier'
up_path = 'uploads'
down_path = 'results'



# Create Azure file service connection
# Get the user uploaded file from Azure File Service and read data
def get_file(filename):    
    

    file_service.get_file_to_path (path1, up_path, filename, filename)

    # Read data
    df = pd.read_excel(filename, 'data')
    df = pd.DataFrame(df)
    
    return df



# Extract Variables
def get_variables(filename): 
    df = get_file(filename)
    cost_max = math.ceil (sum (df['Cost']))
    cost_min = int (min (df['Cost']))
    step = int ((cost_max - cost_min)/100)
    budget_list = list(range (cost_min, cost_max, step))
    budget_list.append(cost_max)

    return df, budget_list




# Create the optimization function
def optfunc (df, budget):
    # Define the lp problem
    prob = pl.LpProblem('ProjectSelection', pl.LpMaximize)
    # Create the weights
    weights=[]
    for rownum, row in df.iterrows():
        weightstr = str ('w' + str(rownum))  #Create naming of variables
        weight = pl.LpVariable (str(weightstr), lowBound = 0, upBound = 1, cat = 'Integer')
        weights.append(weight)
    
    # Create the optimization function
    total_profit = ""
    for rownum, row in df.iterrows():
        for i, w in enumerate(weights):
            if rownum == i:
                total_profit += row['Benefit'] * w
    prob += total_profit
    
    # Create constrains
    total_cost = ""
    for rownum, row in df.iterrows():
        for i, s in enumerate(weights):
            if rownum == i:
                total_cost += row['Cost'] * s
    prob += (total_cost <= budget)
    
    # Run optimization
    opt_res = prob.solve()
    sum_profit = pl.value(prob.objective)
    
    # Create a dictionary for v.varValue = 1
    d = {int(v.name[1:]) : v.varValue for v in prob.variables() if v.varValue > 0}
    key_list = list (d.keys())
    value_list = list(d.values())
    
    # Calculate actual total_cost
    ind_cost = []
    for n in key_list:
        c = df.loc[n, 'Cost']
        ind_cost.append(c)
    
    # Define the returns
    sum_profit = round(pl.value(prob.objective), 1)
    #sum_cost_1 = sum([i*j for i, j in zip(value_list, ind_cost)])
    #sum_cost_1 = round (float(sum_cost_1), 1)
    
    sum_cost_2 = float(np.dot(value_list, ind_cost))
    sum_cost_2 = round (sum_cost_2, 1)
    p_list = []
    for pc in key_list:
        p = df[df.index == pc]['Name']
        name = p.base[0][0]
        p_list.append(name)
    
    return [budget, sum_cost_2, sum_profit, p_list]

#optfunc(df,   1207394.00)





# Convert the set of results for different budgets into dataframe and dictionary, then write an output file and upload it to Azure
def get_result(filename, plot = False):    
    df, budget_list = get_variables(filename)
    res_list = []
    for i in budget_list:
        ind_res = optfunc(df, i)
        res_list.append(ind_res)
    res_df = pd.DataFrame(res_list, columns = ['Budget', 'Cost', 'Benefit', 'Included:'])
    
    res_dict = res_df.to_dict('split')


    if plot:
        plt.scatter(res_df['Budget'], res_df['Benefit'])
        plt.show()


    # Write the result to xlsx and create scatter chart
    out_file_name = 'Result_' + filename
    df_e = pd.DataFrame()
    x_axis = res_df['Budget']
    y_axis = res_df['Benefit']

    writer = pd.ExcelWriter (out_file_name, engine = 'xlsxwriter')
    res_df.to_excel(writer, 'Data')
    df_e.to_excel(writer, 'Chart')
    y_major = (max(y_axis) - min(y_axis))/20

    # Access the XlsxWriter workbook and worksheet objects from the dataframe
    workbook = writer.book
    worksheet1 = writer.sheets['Data']
    worksheet2 = writer.sheets['Chart']

    # Add cell formats

    format1 = workbook.add_format({'num_format': '$###,###,###,###,##0.0'})
    worksheet1.set_column ('B:D', 18, format1)

    # Create series for charts
    series1 = '=Data!$B$1:$B$' + str(len(x_axis) + 1)
    series2 = '=Data!$D$1:$D$' + str(len(y_axis) + 1)

    # Create a chart object
    chart1 = workbook.add_chart({'type': 'scatter'})

    # Configure the series of the chart from the data
    chart1.add_series({'categories': series1,
        'values': series2,
        'name' : 'Portfolio'})

    # Format the chart
    chart1.set_x_axis({'name': 'Budget Levels',
                    'num_format': '0',
                    'major_unit': 5
                    })
    chart1.set_y_axis({'name': 'Portfolio Benefits (in Millions)',
                    'num_format': '$0.0',
                    'display_units': 'millions',
                    'display_units_visible': False,
                    'major_unit': y_major
                    })
    chart1.set_title ({'name': 'Efficient Frontier'})
    chart1.set_style(14)
    chart1.set_size ({'width': 1200, 'height': 750})

    # Insert the chart
    worksheet2.insert_chart('A1', chart1, {'x_oofset': 25, 'y_offset': 10})

    # Close
    workbook.close()
    writer.save()


    # Upload the output file to Azure File Service
    file_service.create_file_from_path(
    path1, down_path, out_file_name, out_file_name)
 
    # out_file_path = path1 + '/' + path2 + '/' + out_file_name

    # Delete the files from local
    os.remove(filename)
    os.remove(out_file_name)



    return res_dict, AzureStorageAccount, path1, down_path, out_file_name, key



