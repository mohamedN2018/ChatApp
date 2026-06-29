import { useUiStore } from '~/stores/ui'

// Lightweight i18n (English/Arabic). The backend negotiates message language via
// the X-Language header; the UI strings live here for snappy switching + RTL.
const messages: Record<string, Record<string, string>> = {
  en: {
    'app.name': 'ChatApp',
    'auth.login': 'Sign in',
    'auth.register': 'Create account',
    'auth.email': 'Email',
    'auth.username': 'Username',
    'auth.password': 'Password',
    'auth.confirm': 'Confirm password',
    'auth.noAccount': "Don't have an account?",
    'auth.haveAccount': 'Already have an account?',
    'auth.welcome': 'Welcome back',
    'auth.join': 'Join ChatApp',
    'auth.registered': 'Account created — check your email to verify, then sign in.',
    'chat.conversations': 'Conversations',
    'chat.newChat': 'New chat',
    'chat.startBy': 'Start a chat by username',
    'chat.placeholder': 'Type a message…',
    'chat.empty': 'Select a conversation to start chatting',
    'chat.typing': 'typing…',
    'common.send': 'Send',
    'common.logout': 'Log out',
    'common.online': 'Online',
    'common.offline': 'Offline',
    'common.search': 'Search…',
  },
  ar: {
    'app.name': 'تشات آب',
    'auth.login': 'تسجيل الدخول',
    'auth.register': 'إنشاء حساب',
    'auth.email': 'البريد الإلكتروني',
    'auth.username': 'اسم المستخدم',
    'auth.password': 'كلمة المرور',
    'auth.confirm': 'تأكيد كلمة المرور',
    'auth.noAccount': 'ليس لديك حساب؟',
    'auth.haveAccount': 'لديك حساب بالفعل؟',
    'auth.welcome': 'مرحبًا بعودتك',
    'auth.join': 'انضم إلى تشات آب',
    'auth.registered': 'تم إنشاء الحساب — تحقق من بريدك ثم سجّل الدخول.',
    'chat.conversations': 'المحادثات',
    'chat.newChat': 'محادثة جديدة',
    'chat.startBy': 'ابدأ محادثة باسم المستخدم',
    'chat.placeholder': 'اكتب رسالة…',
    'chat.empty': 'اختر محادثة لبدء الدردشة',
    'chat.typing': 'يكتب…',
    'common.send': 'إرسال',
    'common.logout': 'تسجيل الخروج',
    'common.online': 'متصل',
    'common.offline': 'غير متصل',
    'common.search': 'بحث…',
  },
}

export function useT() {
  const ui = useUiStore()
  return (key: string): string => messages[ui.locale]?.[key] ?? messages.en[key] ?? key
}
