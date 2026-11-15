class RetryStrategy:
    """Manages retry logic for translation batches."""
    
    def __init__(self, max_attempts: int = 5):
        self.max_attempts = max_attempts
        
    def should_retry(self, attempt: int) -> bool:
        """Determine if another attempt should be made."""
        return attempt < self.max_attempts
        
    def get_instructions_for_attempt(self, attempt: int, missing_ids: list = None, is_allam: bool = False) -> str:
        """Get specific instructions based on attempt number."""
        if attempt == 1:
            return ""
            
        if is_allam:
            base = "تنبيه هام للمحاولة السابقة: اكتب رقم كل سطر بدقة داخل القوسين مثل [128]، ممنوع منعاً باتاً ترك القوسين فارغين هكذا [ ] وممنوع حذف الأرقام! "
            if missing_ids:
                base += f"الأسطر ذات الأرقام التالية فُقدت ويجب كتابة أرقامها وترجمتها سطراً بسطر: {missing_ids}."
            else:
                base += "تأكد من ترجمة كل سطر وكتابة رقمه داخل القوسين بدقة دون تخطي."
            return base

        base = "تنبيه للمحاولة السابقة: التزم بالصيغة الإلزامية [الرقم] النص المترجم مباشرة بدون أي كلام تمهيدي أو ماركداون وبدون ترك القوسين فارغين هكذا [ ]. "
        
        if missing_ids:
            base += f"الأسطر ذات المعرفات التالية فُقدت في الرد السابق ويجب ترجمتها وتضمينها بأرقامها: {missing_ids}."
        else:
            base += "تأكد من ترجمة كل سطر بنفس رقمه بدقة دون دمج أو تخطي."
            
        return base
