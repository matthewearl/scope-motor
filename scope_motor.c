#include <stdlib.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/signal.h>
#include <avr/pgmspace.h>

#include "uart.h"

/* 38400 baud */
#define UART_BAUD_RATE      38400


#define PWM_PORT            PORTB
#define PWM_DIR             DDRB
#define PWM_BIT             1
 

volatile unsigned int on_time = 128;
volatile unsigned int on_phase = 0;

ISR(TIMER0_OVF_vect)
{
    if (on_phase < on_time) {
        PWM_PORT |= 1 << PWM_BIT;
    } else {
        PWM_PORT &= ~(1 << PWM_BIT);
    }

    //PWM_PORT |= 1 << PWM_BIT;

    if (on_phase == 0xFF) {
        on_phase = 0;
    } else {
        on_phase++;
    }
}

volatile unsigned int adc_divider = 0;

ISR(ADC_vect)
{
    if (adc_divider == 10) {
        uart_putc(ADCH);
        adc_divider = 0;
    } else {
        adc_divider++;
    }
}


int main(void)
{
    unsigned int i;
    unsigned int c;
    
    // Set up UART.
    uart_init(UART_BAUD_SELECT(UART_BAUD_RATE,F_CPU)); 

    // Enable interrupts.
    sei();

    // Set up timer to poll at 62500 Hz = 16 MHz / 256
    TCCR0B = 1 << CS00;
    TIMSK0 = 1 << TOIE0;

    // Setup the ADC: 
    //  * 1.1V internal voltage ref.
    //  * Left-adjusted result.
    //  * ADC5 (pin 28) input.
    //  * Enable ADC, and start conversion.
    //  * Auto-triggering enable.
    //  * Set ADC clock to 16 MHz / 128.
    //  * Set auto-trigger to free-running mode.
    ADMUX = 1 << REFS0 | 1 << REFS1 |
            1 << ADLAR |
            1 << MUX2 | 1 << MUX0;
    ADCSRA = 1 << ADEN | 1 << ADSC |
             1 << ADATE |
             1 << ADPS2 | 1 << ADPS1 | 1 << ADPS0 ;
    ADCSRB = 0;

    // Set up PWM pin as an output.
    PWM_DIR |= 1 << PWM_BIT;

    while (1) {
        c = uart_getc();
        if (c == 1) {
            for (i = 0; i < 100; i++) {
                uart_putc(ADCH);
            }
        } else if (c == 2) {
            uart_puts("Hello\n");
        } else if (c == 3) {
            while ((c = uart_getc()) != UART_NO_DATA);
            on_time = (unsigned int)c;
        }
    }

    return (0);
}

