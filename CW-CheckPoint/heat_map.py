import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
# Data with responses from 5 participants for 16 questions in my usability questionnaire
data = {
    "Question 01": [4, 3, 4, 3, 2],
    "Question 02": [3, 4, 3, 3, 4],
    "Question 03": [2, 4, 4, 4, 3],
    "Question 04": [4, 2, 2, 2, 3],
    "Question 05": [3, 2, 4, 5, 2],
    "Question 06": [2, 3, 2, 1, 5],
    "Question 07": [4, 2, 4, 1, 2],
    "Question 08": [4, 4, 1, 2, 5],
    "Question 09": [3, 4, 4, 3, 3],
    "Question 10": [4, 2, 2, 2, 4],
    "Question 11": [2, 3, 4, 4, 2],
    "Question 12": [4, 2, 2, 3, 3],
    "Question 13": [3, 4, 3, 4, 2],
    "Question 14": [2, 2, 2, 2, 4],
    "Question 15": [3, 2, 4, 4, 2],
    "Question 16": [4, 4, 2, 3, 2]
}

df = pd.DataFrame(data)
# Convert DataFrame to long format for easier plotting
df_long = df.melt(var_name="Question", value_name="Response")
# Create a pivot table for the heatmap
response_pivot = df_long.pivot_table(index="Question", columns="Response",
aggfunc=len, fill_value=0)
# Create a heatmap
plt.figure(figsize=(12, 8))
sns.heatmap(response_pivot, annot=True, cmap="YlGnBu", fmt="d")
plt.title("Likert Scale Questionnaire Responses (3 Participants)")
plt.ylabel("Question")
plt.xlabel("Response")
plt.show()