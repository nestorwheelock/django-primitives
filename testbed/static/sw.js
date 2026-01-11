/**
 * Service Worker for Push Notifications
 * Handles push events and notification clicks for the customer portal.
 */

const CACHE_VERSION = 'v1';
const OFFLINE_URL = '/portal/offline/';

// Handle push events from the server
self.addEventListener('push', function(event) {
    console.log('[Service Worker] Push received');

    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            console.warn('[Service Worker] Push data was not JSON:', e);
            data = { body: event.data.text() };
        }
    }

    const title = data.title || 'New Notification';
    const options = {
        body: data.body || 'You have a new message',
        icon: '/static/images/icon-192.png',
        badge: '/static/images/badge-72.png',
        tag: data.tag || 'notification-' + Date.now(),
        data: {
            url: data.url || '/portal/',
            timestamp: data.timestamp || new Date().toISOString()
        },
        requireInteraction: true,
        vibrate: [200, 100, 200],
        actions: [
            {
                action: 'open',
                title: 'View',
                icon: '/static/images/action-open.png'
            },
            {
                action: 'dismiss',
                title: 'Dismiss',
                icon: '/static/images/action-close.png'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', function(event) {
    console.log('[Service Worker] Notification click received');

    event.notification.close();

    const action = event.action;
    const url = event.notification.data.url || '/portal/';

    if (action === 'dismiss') {
        // Just close the notification
        return;
    }

    // Open or focus the appropriate window
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(function(clientList) {
                // Check if there's already a window open
                for (let i = 0; i < clientList.length; i++) {
                    const client = clientList[i];
                    if (client.url.includes('/portal/') && 'focus' in client) {
                        // Navigate existing window to the URL
                        client.navigate(url);
                        return client.focus();
                    }
                }
                // Open a new window
                if (clients.openWindow) {
                    return clients.openWindow(url);
                }
            })
    );
});

// Handle notification close (without click)
self.addEventListener('notificationclose', function(event) {
    console.log('[Service Worker] Notification was closed', event);
});

// Service worker activation
self.addEventListener('activate', function(event) {
    console.log('[Service Worker] Activating...');

    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.filter(function(cacheName) {
                    // Delete old caches
                    return cacheName.startsWith('portal-') && cacheName !== 'portal-' + CACHE_VERSION;
                }).map(function(cacheName) {
                    return caches.delete(cacheName);
                })
            );
        }).then(function() {
            // Take control of all clients immediately
            return self.clients.claim();
        })
    );
});

// Service worker installation
self.addEventListener('install', function(event) {
    console.log('[Service Worker] Installing...');

    event.waitUntil(
        // Skip waiting to activate immediately
        self.skipWaiting()
    );
});

// Handle push subscription change (browser renewed subscription)
self.addEventListener('pushsubscriptionchange', function(event) {
    console.log('[Service Worker] Push subscription changed');

    event.waitUntil(
        self.registration.pushManager.subscribe({ userVisibleOnly: true })
            .then(function(subscription) {
                // Re-subscribe on the server
                return fetch('/portal/push/resubscribe/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        oldEndpoint: event.oldSubscription ? event.oldSubscription.endpoint : null,
                        newSubscription: subscription.toJSON()
                    })
                });
            })
    );
});
