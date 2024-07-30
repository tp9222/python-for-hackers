import pandas as pd
import sys

# Define the function to process the CSV file and produce the output
def process_nessus_csv(file_path):
    # Read the CSV file
    df = pd.read_csv(file_path)
    
    # Convert Protocol to uppercase
    df['Protocol'] = df['Protocol'].str.upper()
    
    # Drop duplicate rows
    df = df.drop_duplicates(subset=['Host', 'Protocol', 'Port'])
    
    # Group by Host and Protocol, and aggregate Ports
    output_df = df.groupby(['Host', 'Protocol'])['Port'].apply(lambda x: ', '.join(map(str, sorted(x)))).reset_index()
    
    # Create the desired output format
    output_df['Output'] = output_df.apply(lambda row: f"{row['Host']} {row['Protocol']} {row['Port']}", axis=1)
    
    # Save the result to output.txt
    output_df[['Output']].to_csv('output.txt', index=False, header=False)
    
    # Return the result
    return output_df[['Output']]

if __name__ == "__main__":
    # Check if the file path is provided
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_nessus_csv>")
    else:
        # Get the file path from the command line argument
        file_path = sys.argv[1]
        
        # Process the CSV file and print the result
        result = process_nessus_csv(file_path)
        print(result)
