import stripe
import paypalrestsdk
from django.conf import settings
from django.urls import reverse
from decimal import Decimal
import logging
import uuid

logger = logging.getLogger(__name__)
#REMOVE THIS COMMENT WHEN YOU RETURN
# Initialize Stripe
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

# Initialize PayPal
paypalrestsdk.configure({
    "mode": getattr(settings, 'PAYPAL_MODE', 'sandbox'),  # sandbox or live
    "client_id": getattr(settings, 'PAYPAL_CLIENT_ID', ''),
    "client_secret": getattr(settings, 'PAYPAL_CLIENT_SECRET', '')
})

class PaymentGatewayError(Exception):
    """Custom exception for payment gateway errors"""
    pass

class StripePaymentGateway:
    """Stripe payment processing"""
    
    @staticmethod
    def create_payment_intent(amount, currency='usd', metadata=None):
        """Create a Stripe PaymentIntent"""
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)
            
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            
            return {
                'success': True,
                'payment_intent_id': intent.id,
                'client_secret': intent.client_secret,
                'status': intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def confirm_payment(payment_intent_id):
        """Confirm a Stripe payment"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                'success': True,
                'status': intent.status,
                'amount': intent.amount / 100,  # Convert back from cents
                'payment_method': intent.payment_method
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe confirmation error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def create_refund(payment_intent_id, amount=None):
        """Create a refund for a Stripe payment"""
        try:
            refund_data = {'payment_intent': payment_intent_id}
            if amount:
                refund_data['amount'] = int(amount * 100)  # Convert to cents
            
            refund = stripe.Refund.create(**refund_data)
            
            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'amount': refund.amount / 100
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

class PayPalPaymentGateway:
    """PayPal payment processing"""
    
    @staticmethod
    def create_payment(amount, currency='USD', return_url=None, cancel_url=None, description=""):
        """Create a PayPal payment"""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url
                },
                "transactions": [{
                    "item_list": {
                        "items": [{
                            "name": description,
                            "sku": str(uuid.uuid4())[:8],
                            "price": str(amount),
                            "currency": currency,
                            "quantity": 1
                        }]
                    },
                    "amount": {
                        "total": str(amount),
                        "currency": currency
                    },
                    "description": description
                }]
            })
            
            if payment.create():
                # Get approval URL
                approval_url = None
                for link in payment.links:
                    if link.rel == "approval_url":
                        approval_url = link.href
                        break
                
                return {
                    'success': True,
                    'payment_id': payment.id,
                    'approval_url': approval_url,
                    'status': payment.state
                }
            else:
                logger.error(f"PayPal payment creation error: {payment.error}")
                return {
                    'success': False,
                    'error': str(payment.error)
                }
                
        except Exception as e:
            logger.error(f"PayPal error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def execute_payment(payment_id, payer_id):
        """Execute a PayPal payment after approval"""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            
            if payment.execute({"payer_id": payer_id}):
                return {
                    'success': True,
                    'payment_id': payment.id,
                    'status': payment.state,
                    'amount': float(payment.transactions[0].amount.total)
                }
            else:
                logger.error(f"PayPal execution error: {payment.error}")
                return {
                    'success': False,
                    'error': str(payment.error)
                }
                
        except Exception as e:
            logger.error(f"PayPal execution error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def create_refund(sale_id, amount=None):
        """Create a refund for a PayPal payment"""
        try:
            sale = paypalrestsdk.Sale.find(sale_id)
            
            refund_data = {}
            if amount:
                refund_data = {
                    "amount": {
                        "total": str(amount),
                        "currency": "USD"
                    }
                }
            
            refund = sale.refund(refund_data)
            
            if refund.success():
                return {
                    'success': True,
                    'refund_id': refund.id,
                    'status': refund.state,
                    'amount': float(refund.amount.total) if refund.amount else amount
                }
            else:
                logger.error(f"PayPal refund error: {refund.error}")
                return {
                    'success': False,
                    'error': str(refund.error)
                }
                
        except Exception as e:
            logger.error(f"PayPal refund error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

class PaymentGatewayFactory:
    """Factory class to get the appropriate payment gateway"""
    
    GATEWAYS = {
        'stripe': StripePaymentGateway,
        'paypal': PayPalPaymentGateway,
    }
    
    @classmethod
    def get_gateway(cls, payment_method):
        """Get payment gateway based on payment method"""
        if payment_method in ['stripe', 'credit_card', 'debit_card', 'visa', 'mastercard', 'amex', 'discover']:
            return cls.GATEWAYS.get('stripe')
        elif payment_method == 'paypal':
            return cls.GATEWAYS.get('paypal')
        else:
            raise PaymentGatewayError(f"Unsupported payment method: {payment_method}")
    
    @classmethod
    def process_payment(cls, payment_method, amount, **kwargs):
        """Process payment using the appropriate gateway"""
        gateway = cls.get_gateway(payment_method)
        
        if not gateway:
            raise PaymentGatewayError(f"No gateway found for payment method: {payment_method}")
        
        if payment_method in ['stripe', 'credit_card', 'debit_card', 'visa', 'mastercard', 'amex', 'discover']:
            return gateway.create_payment_intent(amount, **kwargs)
        elif payment_method == 'paypal':
            return gateway.create_payment(amount, **kwargs)
        else:
            raise PaymentGatewayError(f"Unsupported payment processing for: {payment_method}")
