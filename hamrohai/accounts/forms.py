from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()



# RegisterForm with first_name, last_name, age
class RegisterForm(forms.Form):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Ism'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Familya'}))
    age = forms.IntegerField(min_value=0, widget=forms.NumberInput(attrs={'placeholder': 'Yosh'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email kiriting'}))
    password = forms.CharField(min_length=6, widget=forms.PasswordInput(attrs={'placeholder': 'Parol yarating (6+ belgi)'}))

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return email


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email kiriting'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Parol'})
    )
