/* Validate real OSRM driving alternatives before any simulation or camera query.
   No network, storage, identity or license-plate tracking. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.KatoptronRouting = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';
  const validUS = p => Array.isArray(p) && p.length === 2 &&
    Number.isFinite(p[0]) && Number.isFinite(p[1]) &&
    p[0]>=17 && p[0]<=72 && p[1]>=-180 && p[1]<=-64;

  function readAlternatives(data, from, to, geo) {
    if (!geo || typeof geo.haversine !== 'function')
      throw new Error('Road geometry verifier unavailable');
    if (data?.code !== 'Ok' || !Array.isArray(data.routes) || !data.routes.length)
      throw new Error('No driving route was returned. Try more specific destinations.');
    if (!validUS(from.point) || !validUS(to.point))
      throw new Error('Only US destinations are supported');
    const result=[];
    for(const item of data.routes.slice(0,3)) {
      const coords=item?.geometry?.coordinates;
      if (item.geometry?.type !== 'LineString' || !Array.isArray(coords) ||
        coords.length < 2 || coords.length > 20000 ||
        !Number.isFinite(item.distance) || item.distance<=0 ||
        item.distance>12000000 || !Number.isFinite(item.duration) ||
        item.duration<=0 || item.duration>1209600)
        throw new Error('The routing service returned incomplete driving geometry');
      const points=coords.map(c=>[Number(c?.[1]),Number(c?.[0])]);
      if(points.some(p=>!validUS(p)) ||
         geo.haversine(points[0],from.point)>5000 ||
         geo.haversine(points[points.length-1],to.point)>5000)
        throw new Error('Driving route geometry does not match US destinations');
      const candidate={points,distance:item.distance,duration:item.duration,
        from:from.label,to:to.label};
      // A routing provider can return equivalent alternatives twice.
      if(!result.some(p=>p.points.length===points.length &&
         Math.abs(p.distance-item.distance)<1 &&
         Math.abs(p.duration-item.duration)<1))result.push(candidate);
    }
    if(!result.length)throw new Error('No verified driving alternative was returned');
    return result;
  }
  return Object.freeze({readAlternatives});
});
