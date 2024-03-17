import tkinter as tk
from tkinter import messagebox

class MCQExam(tk.Tk):
    def __init__(self, questions_file):
        super().__init__()
        self.title("MCQ Exam")
        self.geometry("500x300")

        self.questions = self.load_questions(questions_file)
        self.current_question_index = 0
        self.selected_answer = tk.StringVar()

        self.question_label = tk.Label(self, text="")
        self.question_label.pack(pady=10)

        self.radio_buttons = []
        for i in range(4):
            radio_button = tk.Radiobutton(self, text="", variable=self.selected_answer, value=str(i))
            radio_button.pack(anchor="w")
            self.radio_buttons.append(radio_button)

        self.submit_button = tk.Button(self, text="Submit", command=self.submit_answer)
        self.submit_button.pack(pady=10)

        self.display_question()

    def load_questions(self, file_path):
        questions = []
        with open(file_path, 'r') as file:
            lines = file.readlines()
            question_data = None
            for line in lines:
                if line.strip() == "EOQ":
                    if question_data:
                        questions.append(question_data)
                    question_data = None
                elif line.strip() == "EOX":
                    break
                elif question_data is None:
                    question_data = {"question": line.strip(), "answers": [], "correct_answer": ""}
                else:
                    if line.startswith("Answer"):
                        question_data["correct_answer"] = line.split(":")[1].strip()
                    else:
                        question_data["answers"].append(line.strip())
        print(questions)  # Debugging print statement
        return questions

    def display_question(self):
        question_data = self.questions[self.current_question_index]
        self.question_label.config(text=question_data["question"])

        for i in range(4):
            if i < len(question_data["answers"]):
                self.radio_buttons[i].config(text=question_data["answers"][i])
            else:
                self.radio_buttons[i].config(text="")

    def submit_answer(self):
        selected_index = int(self.selected_answer.get())
        correct_answer_letter = self.questions[self.current_question_index]["correct_answer"]
        correct_answer_index = ord(correct_answer_letter) - ord('A')
        
        if selected_index == correct_answer_index:
            messagebox.showinfo("Result", "Correct!")
        else:
            messagebox.showerror("Result", f"Wrong! Correct answer is {correct_answer_letter}")

        self.current_question_index += 1
        self.selected_answer.set("")
        
        if self.current_question_index < len(self.questions):
            self.display_question()
        else:
            messagebox.showinfo("End of Exam", "You have completed the exam.")

if __name__ == "__main__":
    app = MCQExam("questions.txt")
    app.mainloop()
