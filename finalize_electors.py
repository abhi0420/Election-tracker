"""
Final cleanup script to fix name mismatches and complete the electors_after_deletion.csv
"""

import pandas as pd

def fix_names_and_merge():
    # Read both files
    pdf_data = pd.read_csv('pdf_extracted_electors.csv')
    deletions = pd.read_csv('deleted_voters_per_seat.csv')
    
    print(f"PDF data: {len(pdf_data)} constituencies")
    print(f"Deletions data: {len(deletions)} constituencies")
    
    # Fix the Kusheshwar Asthan name in PDF data
    pdf_data.loc[pdf_data['Assembly Constituency'] == 'Kusheshwar Asthan', 'Assembly Constituency'] = 'Kusheshwar Asthan (SC)'
    
    # For the two "Pipra" constituencies, we need to handle them specially
    # Looking at the AC numbers from PDF:
    # AC 17 is Pipra (East Champaran - Purvi Champaran)
    # AC 42 is Pipra (Supaul)
    
    # Split deletions for the two Pipras
    pipra_ec = deletions[deletions['Assembly Constituency'] == 'Pipra, Purvi Champaran'].iloc[0]['Total Deletions'] if len(deletions[deletions['Assembly Constituency'] == 'Pipra, Purvi Champaran']) > 0 else 35045
    pipra_supaul = deletions[deletions['Assembly Constituency'] == 'Pipra, Supaul'].iloc[0]['Total Deletions'] if len(deletions[deletions['Assembly Constituency'] == 'Pipra, Supaul']) > 0 else 21803
    
    print(f"\nPipra (Purvi Champaran) deletions: {pipra_ec:,}")
    print(f"Pipra (Supaul) deletions: {pipra_supaul:,}")
    
    # Remove old Pipra entries from deletions
    deletions = deletions[~deletions['Assembly Constituency'].str.contains('Pipra', na=False)]
    
    # Add the two Pipras back with correct names
    new_pipra_rows = pd.DataFrame([
        {'Assembly Constituency': 'Pipra, Purvi Champaran', 'Total Deletions': pipra_ec},
        {'Assembly Constituency': 'Pipra, Supaul', 'Total Deletions': pipra_supaul}
    ])
    deletions = pd.concat([deletions, new_pipra_rows], ignore_index=True)
    
    # Now merge with PDF data
    # First, create a mapping for the two Pipras in PDF data
    pdf_data_fixed = pdf_data.copy()
    
    # AC 17 = Pipra, Purvi Champaran
    # AC 42 = Pipra, Supaul
    pdf_data_fixed.loc[pdf_data_fixed['AC_No'] == 17, 'Assembly Constituency'] = 'Pipra, Purvi Champaran'
    pdf_data_fixed.loc[pdf_data_fixed['AC_No'] == 42, 'Assembly Constituency'] = 'Pipra, Supaul'
    
    # Handle Sheohar (AC 22) - might be missing from PDF
    sheohar_row = pd.DataFrame([{
        'AC_No': 22,
        'Assembly Constituency': 'Sheohar',
        'Total_Electors_Before_Deletion': 321924  # From the extracted text
    }])
    
    # Check if Sheohar is already in PDF data
    if len(pdf_data_fixed[pdf_data_fixed['Assembly Constituency'] == 'Sheohar']) == 0:
        pdf_data_fixed = pd.concat([pdf_data_fixed, sheohar_row], ignore_index=True)
        print("\n✓ Added missing Sheohar constituency")
    
    # Now merge
    merged = pdf_data_fixed.merge(
        deletions,
        on='Assembly Constituency',
        how='outer',
        indicator=True
    )
    
    # Check results
    both = merged[merged['_merge'] == 'both']
    only_pdf = merged[merged['_merge'] == 'left_only']
    only_deletions = merged[merged['_merge'] == 'right_only']
    
    print(f"\nMerge results:")
    print(f"  Matched: {len(both)}")
    print(f"  Only in PDF: {len(only_pdf)}")
    print(f"  Only in deletions: {len(only_deletions)}")
    
    if len(only_pdf) > 0:
        print("\n⚠️ Only in PDF:")
        for _, row in only_pdf.iterrows():
            print(f"  AC {row['AC_No']}: {row['Assembly Constituency']}")
    
    if len(only_deletions) > 0:
        print("\n⚠️ Only in deletions:")
        for _, row in only_deletions.iterrows():
            print(f"  {row['Assembly Constituency']}")
    
    # Fill missing values
    merged['Total_Electors_Before_Deletion'] = merged['Total_Electors_Before_Deletion'].fillna(0)
    merged['Total Deletions'] = merged['Total Deletions'].fillna(0)
    
    # Calculate electors after deletion
    merged['Total_Electors_After_Deletion'] = (
        merged['Total_Electors_Before_Deletion'] - merged['Total Deletions']
    )
    
    # Select final columns
    final = merged[['AC_No', 'Assembly Constituency', 
                    'Total_Electors_Before_Deletion',
                    'Total Deletions',
                    'Total_Electors_After_Deletion']].copy()
    
    # Sort by AC number
    final = final.sort_values('AC_No').reset_index(drop=True)
    
    # Save to CSV
    output_file = 'electors_after_deletion.csv'
    final.to_csv(output_file, index=False)
    
    print(f"\n{'='*80}")
    print(f"✅ SUCCESS! Final data saved to: {output_file}")
    print(f"{'='*80}")
    
    print(f"\n📊 SUMMARY:")
    print(f"Total Constituencies: {len(final)}")
    print(f"Total Electors Before Deletion: {final['Total_Electors_Before_Deletion'].sum():>20,.0f}")
    print(f"Total Deletions:                {final['Total Deletions'].sum():>20,.0f}")
    print(f"Total Electors After Deletion:  {final['Total_Electors_After_Deletion'].sum():>20,.0f}")
    print(f"Deletion Rate:                  {(final['Total Deletions'].sum() / final['Total_Electors_Before_Deletion'].sum() * 100):>19.2f}%")
    
    print(f"\n🔝 TOP 10 CONSTITUENCIES BY ELECTORS AFTER DELETION:")
    print("-" * 80)
    top10 = final.nlargest(10, 'Total_Electors_After_Deletion')
    for _, row in top10.iterrows():
        print(f"{int(row['AC_No']):3d}. {row['Assembly Constituency']:45s} {row['Total_Electors_After_Deletion']:>10,.0f}")
    
    print(f"\n📉 TOP 10 CONSTITUENCIES BY DELETION RATE:")
    print("-" * 80)
    final_with_rate = final[final['Total_Electors_Before_Deletion'] > 0].copy()
    final_with_rate['Deletion_Rate'] = (final_with_rate['Total Deletions'] / final_with_rate['Total_Electors_Before_Deletion'] * 100)
    top_del_rate = final_with_rate.nlargest(10, 'Deletion_Rate')
    for _, row in top_del_rate.iterrows():
        print(f"{int(row['AC_No']):3d}. {row['Assembly Constituency']:45s} {row['Deletion_Rate']:>6.2f}%")

if __name__ == "__main__":
    fix_names_and_merge()
