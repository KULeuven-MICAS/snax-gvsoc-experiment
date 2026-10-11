#include <stdio.h>
#include <stdint.h>

int main()
{
    uint32_t sum = 0;

    for (int i=0; i<20; i++)
    {
        // Each loaded value is now used, so the core has to wait for it.
        sum += *(volatile uint32_t *)0x00000004;
        sum += *(volatile uint32_t *)0x00000004;
        sum += *(volatile uint32_t *)0x00000004;
        sum += *(volatile uint32_t *)0x00000004;
    }

    printf("sum 0x%x\n", sum);

    return 0;
}