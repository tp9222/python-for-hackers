import pandas as pd

# Define the function to process the CSV file and produce the output
def process_nessus_csv(file_path):
    # Read the CSV file
    df = pd.read_csv(file_path)
    
    # Convert Protocol to uppercase
    df['Protocol'] = df['Protocol'].str.upper()
    
    # Group by Host and Protocol, and aggregate Ports
    output_df = df.groupby(['Host', 'Protocol'])['Port'].apply(lambda x: ', '.join(map(str, sorted(x)))).reset_index()
    
    # Create the desired output format
    output_df['Output'] = output_df.apply(lambda row: f"{row['Host']} {row['Protocol']} {row['Port']}", axis=1)
    
    # Return the result
    return output_df[['Output']]

# Example usage with the provided file
file_path = 'path/to/your/nessus.csv'  # Update this path to the actual file path
result = process_nessus_csv(file_path)
print(result)
