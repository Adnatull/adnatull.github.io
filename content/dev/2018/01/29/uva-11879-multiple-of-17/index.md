---
date: 2018-01-29 13:48:00
title: UVA 11879 - Multiple of 17
tags:
  - UVA Online judge
  - Number Theory
  - Modulus
  - Biginteger
categories:
  - Competitive Programming
  - UVA Online judge
  - Mathematics
  - BigInteger

---

### 11879 - Multiple of 17
Problem Link: https://uva.onlinejudge.org/external/118/11879.pdf

Algorithm: This problem is quite easy. In this, there will be a number which is greater at most 100 digits. So, Its not possible to store it in “long long int” in c++.
<!-- more -->
We will write a program which will take input a string. If the string contains only 0 then the program will be break, otherwise it will enter in another loop. Before entering I will declare two integer variables ‘reminder’ and ‘i’. I will initialize the reminder variable to 0;

```
char s[110];
while(scanf("%s",s)){
 if(strcmp(s,"0")==0)
   break;
 int i, reminder=0;
               //code goes here
       }
```

Then there will be loop which will start from the beginning of string to the end. It will be look like-

```
for(i=0;s[i]!='\0';i++){
   //code goes here
}
```

Now I will multiply the reminder by 10 and sum it with the current digit of the string(due to string case you need to subtract 48 from the current character and it will be count as digit in integer). again I will find the reminder of the previous reminder diving by 17 and will store it in reminder variable. This process continues until the loop ends.

```
reminder=reminder*10+(s[i]-48);
reminder=reminder%17;
```

After the loop ends my program will check whether the reminder variable is zero or not. If it is zero that means the big number(string) is multiple of 17 else it not.

if it is multiple of 17 then my program will print 1 , if this is not multiple of 17 then the program will print 0.

```
if(reminder==0)
     printf("1\n");
   else
     printf("0\n");

```

Now all the steps are done. Now lets combine all the codes in one place.

```
//Problem Link: https://uva.onlinejudge.org/external/118/11879.pdf
//Code Begins
//RUNTIME: 0.00s
#include<cstdio>
#include<cstring>
using namespace std;
int main(){
 char s[110];
 while(scanf("%s",s)){
   if(strcmp(s,"0")==0)
     break;
   int reminder=0;
   for(int i=0;s[i]!='\0';i++){
       reminder=reminder*10+(s[i]-48);
       reminder=reminder%17;
     }
   if(reminder==0)
     printf("1\n");
   else
     printf("0\n");
   }
 return 0;
}
//Code Ends
```
