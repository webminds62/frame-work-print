import React from "react";

/**
 * Web stub for @stripe/stripe-react-native.
 * Native PaymentSheet is iOS/Android only; checkout still works on device builds.
 */
export function StripeProvider(props: {
  children?: React.ReactNode;
  publishableKey?: string;
  urlScheme?: string;
}) {
  return React.createElement(React.Fragment, null, props.children);
}

export function useStripe() {
  return {
    initPaymentSheet: async () => ({
      error: {
        code: "Canceled",
        message:
          "Stripe PaymentSheet is not available on web. Use the iOS or Android app to complete payment.",
      },
    }),
    presentPaymentSheet: async () => ({
      error: {
        code: "Canceled",
        message:
          "Stripe PaymentSheet is not available on web. Use the iOS or Android app to complete payment.",
      },
    }),
  };
}
