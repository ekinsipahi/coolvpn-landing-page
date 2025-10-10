from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf.urls.i18n import i18n_patterns

from landing.views import home  # mevcut home view

Stub = TemplateView.as_view

# --- Namespaced stubs ---
features_patterns = ([
    path('stealth/', Stub(template_name='stubs/simple.html',
                          extra_context={'title': 'Stealth / Obfuscation',
                                         'subtitle': 'Engineered to maximize access on restricted networks'}), name='stealth'),
    path('dedicated-ip/', Stub(template_name='stubs/simple.html',
                               extra_context={'title': 'Dedicated IP / Private Node',
                                              'subtitle': 'Annual plans include your own private endpoint'}), name='dedicated_ip'),
    path('webrtc/', Stub(template_name='stubs/simple.html',
                         extra_context={'title': 'WebRTC Leak Block',
                                        'subtitle': 'Prevent IP leaks in modern browsers'}), name='webrtc'),
    path('split-tunneling/', Stub(template_name='stubs/simple.html',
                                  extra_context={'title': 'Split Tunneling / Whitelist',
                                                 'subtitle': 'Choose what routes through VPN'}), name='split_tunnel'),
], 'features')

advantages_patterns = ([
    path('no-logs/', Stub(template_name='stubs/simple.html',
                          extra_context={'title': 'No-Logs by design',
                                         'subtitle': 'We minimize data by architecture'}), name='no_logs'),
    path('jurisdiction/', Stub(template_name='stubs/simple.html',
                               extra_context={'title': 'Privacy-friendly jurisdiction',
                                              'subtitle': 'Favorable legal base outside surveillance alliances'}), name='jurisdiction'),
    path('speed/', Stub(template_name='stubs/simple.html',
                        extra_context={'title': 'Unlimited bandwidth & high throughput',
                                       'subtitle': 'Optimized network for speed'}), name='speed'),
], 'advantages')

products_patterns = ([
    path('extension/', Stub(template_name='stubs/simple.html',
                            extra_context={'title': 'Browser Extension',
                                           'subtitle': 'Lightweight, control per tab/app'}), name='extension'),
    path('desktop/', Stub(template_name='stubs/simple.html',
                          extra_context={'title': 'Desktop App',
                                         'subtitle': 'System-wide protection'}), name='desktop'),
    path('mobile/', Stub(template_name='stubs/simple.html',
                         extra_context={'title': 'Mobile App',
                                        'subtitle': 'iOS & Android'}), name='mobile'),
], 'products')

blog_patterns = ([
    path('', Stub(template_name='stubs/simple.html',
                  extra_context={'title': 'Blog',
                                 'subtitle': 'Guides, updates, transparency notes'}), name='index'),
], 'blog')

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += i18n_patterns(
    # core routes
    path('admin/', admin.site.urls),
    path('', home, name='home'),

    # auth stubs (navbar'daki login/logout/dashboard/ayarlar için)
    path('login/', Stub(template_name='stubs/simple.html',
                        extra_context={'title': 'Sign in', 'subtitle': 'Magic-link coming soon'}), name='login'),
    path('logout/', Stub(template_name='stubs/simple.html',
                         extra_context={'title': 'Signed out', 'subtitle': 'You have been signed out'}), name='logout'),
    path('dashboard/', Stub(template_name='stubs/simple.html',
                            extra_context={'title': 'Dashboard', 'subtitle': 'Beta placeholder'}), name='dashboard'),
    path('account/settings/', Stub(template_name='stubs/simple.html',
                                   extra_context={'title': 'Account Settings', 'subtitle': 'Manage your account'}), name='account_settings'),

    # marketing
    path('pricing/', Stub(template_name='stubs/simple.html',
                          extra_context={'title': 'Pricing', 'subtitle': 'Choose your plan'}), name='pricing'),
    path('faq/', Stub(template_name='stubs/simple.html',
                      extra_context={'title': 'FAQ', 'subtitle': 'Answers to common questions'}), name='faq'),

    # namespaced groups (navbar namespace'leri)
    path('features/', include(features_patterns)),
    path('advantages/', include(advantages_patterns)),
    path('products/', include(products_patterns)),
    path('blog/', include(blog_patterns)),

    prefix_default_language=False
)
