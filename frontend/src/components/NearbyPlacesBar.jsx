import React from 'react';
import {
  Banknote,
  Building2,
  Fuel,
  Hospital,
  Loader2,
  Navigation,
  ParkingCircle,
  ShoppingBag,
  Star,
  Utensils,
  X,
} from 'lucide-react';
import { formatDistance } from '../utils/geo';

export const NEARBY_CATEGORIES = [
  { id: 'restaurant', label: 'Restaurants', icon: Utensils },
  { id: 'hospital', label: 'Hospitals', icon: Hospital },
  { id: 'fuel', label: 'Petrol', icon: Fuel },
  { id: 'atm', label: 'ATMs', icon: Banknote },
  { id: 'hotel', label: 'Hotels', icon: Building2 },
  { id: 'shopping', label: 'Shopping', icon: ShoppingBag },
  { id: 'parking', label: 'Parking', icon: ParkingCircle },
];

export default function NearbyPlacesBar({
  activeCategory,
  onSelectCategory,
  places,
  loading,
  error,
  onClear,
  onSelectPlace,
  onRouteToPlace,
  onSaveFavorite,
  isNavigating,
}) {
  if (isNavigating) return null;

  return (
    <div className="flex flex-col gap-2 pointer-events-none">
      {/* Category Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar pointer-events-auto">
        {NEARBY_CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const isActive = activeCategory === cat.id;
          return (
            <button
              key={cat.id}
              type="button"
              onClick={() => (isActive ? onClear() : onSelectCategory(cat.id))}
              className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium shadow-map border transition ${
                isActive
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white/95 dark:bg-slate-900/95 text-slate-700 dark:text-slate-200 border-slate-200/80 dark:border-slate-700/80 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {cat.label}
            </button>
          );
        })}
      </div>

      {/* Results Drawer */}
      {(activeCategory || loading || error) && (
        <div className="pointer-events-auto w-full sm:w-[360px] bg-white/95 dark:bg-slate-900/95 backdrop-blur-md rounded-2xl shadow-map border border-slate-200/80 dark:border-slate-700/80 overflow-hidden">
          <div className="px-3.5 py-2.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 uppercase tracking-wider">
              Nearby {NEARBY_CATEGORIES.find((c) => c.id === activeCategory)?.label || 'Places'}
            </p>
            <button
              type="button"
              onClick={onClear}
              aria-label="Close nearby places"
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {loading ? (
            <div className="p-4 flex items-center gap-2.5 text-xs text-slate-500 dark:text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
              Searching OpenStreetMap places nearby...
            </div>
          ) : error ? (
            <div className="p-3.5 text-xs text-amber-700 dark:text-amber-300 bg-amber-50/70 dark:bg-amber-950/30">
              {error}
            </div>
          ) : places.length === 0 ? (
            <div className="p-3.5 text-xs text-slate-500 dark:text-slate-400">
              No places found within 2 km of the current map center.
            </div>
          ) : (
            <div className="max-h-56 overflow-y-auto custom-scrollbar divide-y divide-slate-100 dark:divide-slate-800">
              {places.map((place) => (
                <div
                  key={place.id}
                  onClick={() => onSelectPlace(place)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') onSelectPlace(place);
                  }}
                  className="px-3.5 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/70 cursor-pointer flex items-center justify-between gap-2 transition"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                      {place.name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                      {typeof place.distance_meters === 'number'
                        ? `${formatDistance(place.distance_meters)} away`
                        : 'Nearby'}
                      {place.address ? ` • ${place.address}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSaveFavorite({
                          lat: place.lat,
                          lng: place.lng,
                          label: place.name,
                          category: place.category,
                        });
                      }}
                      title="Save place"
                      className="p-1.5 rounded-lg text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-950/40"
                    >
                      <Star className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRouteToPlace({
                          lat: place.lat,
                          lng: place.lng,
                          label: place.name,
                        });
                      }}
                      title="Directions"
                      className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40"
                    >
                      <Navigation className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
