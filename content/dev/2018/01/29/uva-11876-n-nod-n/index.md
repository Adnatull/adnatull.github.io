---
date: 2018-01-29 13:23:00
title: UVA 11876 - N + NOD (N)
tags:
  - UVA Online judge
  - Number Theory
  - Binary Search
  - Prime Numbers
categories:
  - Competitive Programming
  - UVA Online judge
  - Problem Solving Paradigms
  - Divide and Conquer
  - Binary Search
  - Mathematics
  - Number Theory
  - Prime Numbers

---

### Description:
For a number N, first have to calculate N-1+divisors(N-1) & store it in array (e.g. arr[i]=arr[i-1]+divisors(arr[i-1])).
Make a sequence from 1 to until arr[i] becomes greater than 1000000. Then you will be given two numbers A & B, and you will have to find the number of integers from the above sequence which lies within the range [A,B].

Hints = No critical case. Easy problem.
<!-- more --> 
### Algorithm:
Step 1:
First find the prime numbers from 1 to 1000000 and store them in an array (was not sure about the range, thats why I calculated till 1000000) .
Step 2:
Calculate number of divisors for each numbers from 1 to 1000000 and store divisors in each array. (e.g. divisors of 6 are 1,2,3,6. Total 4 divisors. So divisor[6]=4. )
Step 3: To find the divisors of each number, I took help of prime numbers. There is a good tutorial in lightoj.com to find divisors using primes. Link is give below:
http://lightoj.com/article_show.php?article=1003

To decrease time complexity,
I used here some tricks. First one is, when finding the number of divisors of a value, I checked if it is a prime or not. If the number is a prime then the divisors of that number is 2. Because prime numbers are divisible by 1 and the number it self only.
If the given number is not prime then I again checked if it is a co-prime. Because we know divisors of co-prime is 3 and they are 1, square root of that number(must be integer value, no fraction) and the number it self. So divisors of co-prime is 3.
If the number doesn’t meet the requirement of being prime, co-prime then I followed the algorithm I mentioned at the beginning of this step.
Number of divisors for 1 t0 5. divisor[1]=1, divisor[2]=2, divisor[3]=2, divisor[4]=3, divisor[5]=2, divisor[6]=4.

Step 4: So, I know the number of divisors of values from 1 to 1000000. Now I will calculate the sequence as described in problem description and will store it in a new array (e.g. num[2]=1+divisor[1], so, num[2] = 2, and num[3]=2+divisor[2], so, num[3] = 4).

Step 5: I will take the input as description. For given A & B, I will do binary search here to find lower bound of A and upper bound of B from num array. (the array which I used to store the sequence of numbers from 1 to 1000000) as problem description.
Step 6: Now I will subtract lower bound from upper bound and will save it in a new variable and again I will subtract 1 from this variable and will print this according to instruction. Why I did subtract 1? To understand this I think you need to know how lower bound and upper bound of binary search works!

I am enclosing the code here. Try not to see my code and try your own. Thanks

```
#include<iostream>
#include<algorithm>
#include<cstdio>
#include<cmath>
#define LL long long
#define L long
using namespace std;
L prime[1234567], mark[12345678],m;
void pr () {
    m=0;
    for (int i=4; i<12345678;i+=2)
        mark[i]=1;
    int N=sqrt(12345678)+1;
    for (int i=3;i<N;i+=2) {
        if (!mark[i]) {
            for (int j=i*i;j<12345678;j=j+i*2) {
                mark[j]=1;
            }
        }
    }
    for (int i=2;i<12345678;i++) {
        if(!mark[i])
            prime[m++]=i;
    }
}
bool checkprime( L a ) {
    L left = 0, right = m-1, mid;
    while ( left<=right ) {
        mid = (left+right)/2;
        if(prime[mid]==a)
            return true;
        else if (prime[mid]>a)
            right = mid-1;
        else
            left = mid + 1;
    }
    return false;
}
bool chcekcoprime(L a){
    L x = sqrt(a);
    if(checkprime(x) && x*x==a)
        return true;
    else return false;
}
L num[1234567],di[1234567];
void divisors () {
    L c=2,d,e,f,g;
    di[1]=1;
    for (L i=2;i<1234567;i++){
        d = sqrt(i)+1;
        c=1;
        e=i;
        f=1;
        if(checkprime(i))
            c=2;
        else if (chcekcoprime(i))
            c=3;
        else{
            for (L j=0;prime[j]*prime[j]<=e;j++){
                 f=0;
                while(e%prime[j]==0){
                   f++;
                    e=e/prime[j];
                }
                c*=(f+1);
            }
            if (e>1) c*=2;
        }
        di[i]=c;
    }
    return ;
}
void nu () {
    num[1]=1;
    for (m=2;m<1234567;m++) {
        num[m]=num[m-1]+di[num[m-1]];
        if(num[m]>1234567)
            break;
    }
    return;
}
L lower (L a) {
    L left = 1, right = m, mid;
    while (left<=right) {
        mid = (left+right)/2;
        if(num[mid]==a){
            //cout << mid << endl;
            right=mid-1;
        }
        else if ( num[mid]>a)
            right = mid-1;
        else
            left = mid + 1;
    }
    return right;
}
L upper (L b) {
      L left = 1, right = m, mid;
    while (left<=right) {
        mid = (left+right)/2;
      //  cout << mid << endl;
        if(num[mid]==b){
            left=mid+1;
        }
        else if ( num[mid]>b)
            right = mid-1;
        else
            left = mid + 1;
    }
    return left;
}
int main() {
 //   freopen( "in.txt","r",stdin );
    pr ();
    divisors();
    nu();
    int n;
    L A,B;
    scanf ("%d",&n);
    for (int i=1;i<=n;i++) {
        scanf ("%ld %ld",&A,&B);
        L lo=lower(A), up = upper (B);
        printf ("Case %d: %ld\n",i,up-lo-1);
    }
    return 0;
}
```
