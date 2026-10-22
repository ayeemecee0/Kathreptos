/* Standalone public route geometry: no network, storage, or location tracking. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.KatoptronRouteGeometry = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';
  const R = 6371000;
  const radians = n => n * Math.PI / 180;
  function valid(p) {
    return Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) &&
      Number.isFinite(p[1]) && p[0]>=-90 && p[0]<=90 && p[1]>=-180 && p[1]<=180;
  }
  function haversine(a,b) {
    const dlat=radians(b[0]-a[0]),dlon=radians(b[1]-a[1]);
    const t=Math.sin(dlat/2)**2+Math.cos(radians(a[0]))*
      Math.cos(radians(b[0]))*Math.sin(dlon/2)**2;
    return 2*R*Math.asin(Math.min(1,Math.sqrt(Math.max(0,t))));
  }
  // Short road segments use local equirectangular projection at camera latitude.
  // This measures point-to-street proximity, not actual ALPR read distance.
  function closestOnRoute(point, route) {
    if(!valid(point)||!Array.isArray(route)||route.length<2)
      throw new Error('Invalid route or camera geometry');
    const toXY=(p)=>[
      R*radians(p[1]-point[1])*Math.cos(radians(point[0])),
      R*radians(p[0]-point[0])
    ];
    let cumulative=0,best={distance:Infinity,alongMeters:0,index:0,fraction:0};
    for(let i=0;i<route.length-1;i++){
      const a=route[i],b=route[i+1];
      if(!valid(a)||!valid(b))throw new Error('Invalid route vertex');
      const A=toXY(a),B=toXY(b),vx=B[0]-A[0],vy=B[1]-A[1];
      const norm=vx*vx+vy*vy;
      const f=norm>0?Math.max(0,Math.min(1,-(A[0]*vx+A[1]*vy)/norm)):0;
      const d=Math.hypot(A[0]+f*vx,A[1]+f*vy);
      const seg=haversine(a,b);
      if(d<best.distance)best={distance:d,alongMeters:cumulative+seg*f,index:i,fraction:f};
      cumulative+=seg;
    }
    best.totalMeters=cumulative;
    best.progress=cumulative?best.alongMeters/cumulative:0;
    return best;
  }
  function pointAtProgress(route,progress) {
    if(!Array.isArray(route)||route.length<2)throw new Error('Invalid route');
    const lens=[];let total=0;
    for(let i=0;i<route.length-1;i++){const d=haversine(route[i],route[i+1]);lens.push(d);total+=d;}
    let remaining=total*Math.max(0,Math.min(1,progress));
    for(let i=0;i<lens.length;i++){
      if(remaining<=lens[i]||i===lens.length-1){
        const f=lens[i]?Math.min(1,remaining/lens[i]):0;
        return [route[i][0]+f*(route[i+1][0]-route[i][0]),
          route[i][1]+f*(route[i+1][1]-route[i][1])];
      }
      remaining-=lens[i];
    }
    return route[route.length-1];
  }
  // Subdivide long path segments so camera queries cover the ENTIRE route.
  // 4-degree windows bound density better than one national rectangle.
  function corridorBoxes(points, options={}) {
    const span=options.span||4,pad=options.pad||0.035,max=options.maxBoxes||32;
    if(!Array.isArray(points)||points.length<2||points.length>90000)
      throw new Error('Unsupported route geometry length');
    if(!(span>0&&pad>0&&max>0))throw new Error('Invalid corridor settings');
    let pointsInBox=[],boxes=[];
    const flush=()=>{
      if(pointsInBox.length===0)return;
      const lats=pointsInBox.map(p=>p[0]),lons=pointsInBox.map(p=>p[1]);
      boxes.push({
        south:Math.max(17,Math.min(...lats)-pad),
        west:Math.max(-180,Math.min(...lons)-pad),
        north:Math.min(72,Math.max(...lats)+pad),
        east:Math.min(-64,Math.max(...lons)+pad)
      });
      pointsInBox=[];
      if(boxes.length>max)throw new Error('Route too long for reliable full-coverage search');
    };
    for(let i=0;i<points.length-1;i++){
      const a=points[i],b=points[i+1];
      if(!valid(a)||!valid(b))throw new Error('Invalid coordinates');
      if(a[0]<17||a[0]>72||a[1]<-180||a[1]>-64)
        throw new Error('Route outside the supported US search boundary');
      const pieces=Math.max(1,Math.ceil(Math.max(Math.abs(b[0]-a[0]),Math.abs(b[1]-a[1]))/(span/2)));
      for(let j=0;j<pieces;j++){
        const f=j/pieces,p=[a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1])];
        if(!pointsInBox.length)pointsInBox=[p];
        const lats=pointsInBox.map(x=>x[0]),lons=pointsInBox.map(x=>x[1]);
        if(Math.max(...lats,p[0])-Math.min(...lats,p[0])>span ||
           Math.max(...lons,p[1])-Math.min(...lons,p[1])>span){
          // Include the boundary point on BOTH requests to prevent gaps.
          const previous=pointsInBox[pointsInBox.length-1];
          flush();
          pointsInBox=[previous,p];
        }else pointsInBox.push(p);
      }
    }
    pointsInBox.push(points[points.length-1]);
    flush();
    return boxes.filter(b=>b.south<=b.north&&b.west<=b.east);
  }
  return Object.freeze({haversine,closestOnRoute,pointAtProgress,corridorBoxes});
});