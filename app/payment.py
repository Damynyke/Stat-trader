"""Paystack payment processor integration."""
import os
import httpx
from typing import Optional
from .database import TransactionDB
from sqlmodel import Session

PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackPaymentService:
    """Handle payments through Paystack."""
    
    @staticmethod
    def _get_headers() -> dict:
        """Get Paystack API headers."""
        secret_key = os.getenv("PAYSTACK_SECRET_KEY")
        return {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }
    
    @staticmethod
    def initialize_payment(user_id: str, amount: float, email: str) -> dict:
        """Initialize a Paystack payment."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{PAYSTACK_BASE_URL}/transaction/initialize",
                    headers=PaystackPaymentService._get_headers(),
                    json={
                        "amount": int(amount * 100),  # Convert to kobo (1/100 of naira)
                        "email": email,
                        "metadata": {
                            "user_id": user_id,
                            "transaction_type": "deposit"
                        }
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "authorization_url": data["data"]["authorization_url"],
                        "access_code": data["data"]["access_code"],
                        "reference": data["data"]["reference"],
                        "amount": amount,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Paystack error: {response.text}",
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    @staticmethod
    def verify_payment(reference: str) -> dict:
        """Verify Paystack payment status."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
                    headers=PaystackPaymentService._get_headers(),
                )
                
                if response.status_code == 200:
                    data = response.json()
                    transaction = data["data"]
                    return {
                        "success": transaction["status"] == "success",
                        "status": transaction["status"],
                        "amount": transaction["amount"] / 100,  # Convert from kobo
                        "reference": reference,
                        "customer_email": transaction["customer"]["email"],
                        "user_id": transaction["metadata"].get("user_id"),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Verification failed: {response.text}",
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    @staticmethod
    def process_deposit(user_id: str, reference: str, session: Session) -> dict:
        """Process a successful Paystack payment and update user balance."""
        from .database import UserProfileDB
        from sqlmodel import select
        
        # Verify payment succeeded
        verify_result = PaystackPaymentService.verify_payment(reference)
        if not verify_result["success"]:
            return {"error": "Payment verification failed"}
        
        amount = verify_result["amount"]
        
        # Get user profile
        statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
        profile = session.exec(statement).first()
        if not profile:
            return {"error": "User not found"}
        
        # Create transaction record
        transaction = TransactionDB(
            user_id=user_id,
            transaction_type="deposit",
            amount=amount,
            stripe_id=reference,  # Using same field for Paystack reference
            status="completed"
        )
        session.add(transaction)
        
        # Update balance
        profile.total_balance += amount
        session.add(profile)
        session.commit()
        
        return {
            "success": True,
            "user_id": user_id,
            "amount": amount,
            "reference": reference,
            "new_balance": profile.total_balance,
        }
    
    @staticmethod
    def create_transfer(recipient_code: str, amount: float, reason: str = "Withdrawal") -> dict:
        """Create a withdrawal via Paystack transfer."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{PAYSTACK_BASE_URL}/transfer",
                    headers=PaystackPaymentService._get_headers(),
                    json={
                        "source": "balance",
                        "amount": int(amount * 100),  # Convert to kobo
                        "recipient": recipient_code,
                        "reason": reason,
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "transfer_code": data["data"]["transfer_code"],
                        "reference": data["data"]["reference"],
                        "status": data["data"]["status"],
                        "amount": amount,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Transfer failed: {response.text}",
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class PaystackWebhookHandler:
    """Handle Paystack webhook events."""
    
    @staticmethod
    def verify_signature(payload: bytes, signature: str) -> bool:
        """Verify Paystack webhook signature."""
        import hmac
        import hashlib
        
        secret_key = os.getenv("PAYSTACK_SECRET_KEY")
        hash_obj = hmac.new(secret_key.encode(), payload, hashlib.sha512)
        computed_signature = hash_obj.hexdigest()
        
        return computed_signature == signature
    
    @staticmethod
    def handle_charge_success(event: dict, session: Session) -> dict:
        """Handle successful charge event."""
        data = event.get("data", {})
        reference = data.get("reference")
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        
        if user_id and reference:
            return PaystackPaymentService.process_deposit(user_id, reference, session)
        
        return {"success": False, "error": "Missing user_id or reference"}
    
    @staticmethod
    def handle_charge_failed(event: dict, session: Session) -> dict:
        """Handle failed charge event."""
        data = event.get("data", {})
        reference = data.get("reference")
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        
        if user_id:
            # Log failed transaction
            transaction = TransactionDB(
                user_id=user_id,
                transaction_type="deposit",
                amount=data.get("amount", 0) / 100,
                stripe_id=reference,
                status="failed"
            )
            session.add(transaction)
            session.commit()
            return {"success": True, "status": "failed payment recorded"}
        
        return {"success": False, "error": "Missing user_id"}
    
    @staticmethod
    def handle_transfer_success(event: dict, session: Session) -> dict:
        """Handle successful transfer (withdrawal) event."""
        data = event.get("data", {})
        
        # Log successful withdrawal
        transaction = TransactionDB(
            user_id=data.get("metadata", {}).get("user_id", "unknown"),
            transaction_type="withdrawal",
            amount=data.get("amount", 0) / 100,
            stripe_id=data.get("reference"),
            status="completed"
        )
        session.add(transaction)
        session.commit()
        
        return {"success": True, "status": "withdrawal processed"}
    
    @staticmethod
    def handle_transfer_failed(event: dict, session: Session) -> dict:
        """Handle failed transfer event."""
        data = event.get("data", {})
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        
        if user_id:
            # Log failed withdrawal
            transaction = TransactionDB(
                user_id=user_id,
                transaction_type="withdrawal",
                amount=data.get("amount", 0) / 100,
                stripe_id=data.get("reference"),
                status="failed"
            )
            session.add(transaction)
            session.commit()
            
            # Refund user balance
            from .database import UserProfileDB
            from sqlmodel import select
            
            statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
            profile = session.exec(statement).first()
            if profile:
                profile.total_balance += data.get("amount", 0) / 100
                session.add(profile)
                session.commit()
        
        return {"success": True, "status": "withdrawal failure recorded"}
